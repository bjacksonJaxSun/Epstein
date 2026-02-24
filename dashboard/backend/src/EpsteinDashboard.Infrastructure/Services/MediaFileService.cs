using System.Runtime.InteropServices;
using Amazon;
using Amazon.S3;
using Amazon.S3.Model;
using EpsteinDashboard.Core.Interfaces;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;

namespace EpsteinDashboard.Infrastructure.Services;

/// <summary>
/// Cross-platform media file location service.
/// Translates database paths (Linux VM format) to the current OS
/// using configurable prefix mappings, with fallback to search paths.
/// </summary>
public class MediaFileService : IMediaFileService
{
    private readonly ILogger<MediaFileService> _logger;
    private readonly List<string> _searchPaths;
    private readonly List<PathMapping> _pathMappings;
    private readonly bool _isWindows;
    private readonly AmazonS3Client? _s3Client;
    private readonly string? _r2BucketName;

    public MediaFileService(IConfiguration configuration, ILogger<MediaFileService> logger)
    {
        _logger = logger;
        _searchPaths = new List<string>();
        _pathMappings = new List<PathMapping>();
        _isWindows = RuntimeInformation.IsOSPlatform(OSPlatform.Windows);

        var mediaConfig = configuration.GetSection("MediaFiles");

        // Load path prefix mappings (DB prefix -> local OS path)
        var mappingsSection = mediaConfig.GetSection("PathMappings");
        foreach (var mappingSection in mappingsSection.GetChildren())
        {
            var dbPrefix = mappingSection["DbPrefix"];
            var localPrefix = _isWindows
                ? mappingSection["Windows"]
                : mappingSection["Linux"];

            if (!string.IsNullOrWhiteSpace(dbPrefix) && !string.IsNullOrWhiteSpace(localPrefix))
            {
                _pathMappings.Add(new PathMapping(dbPrefix, localPrefix));
                _logger.LogInformation("Path mapping: {DbPrefix} -> {LocalPrefix}", dbPrefix, localPrefix);
            }
        }

        // Load fallback search paths (only add ones that exist on this OS)
        var pathsSection = mediaConfig.GetSection("SearchPaths");
        foreach (var child in pathsSection.GetChildren())
        {
            var path = child.Value;
            if (!string.IsNullOrWhiteSpace(path) && Directory.Exists(path))
            {
                _searchPaths.Add(path);
                _logger.LogInformation("Media search path configured: {Path}", path);
            }
        }

        // Initialize R2/S3 client if configured
        var r2Config = configuration.GetSection("R2");
        var accountId = r2Config["AccountId"];
        var accessKeyId = r2Config["AccessKeyId"];
        var secretAccessKey = r2Config["SecretAccessKey"];
        _r2BucketName = r2Config["BucketName"];

        if (!string.IsNullOrWhiteSpace(accountId) &&
            !string.IsNullOrWhiteSpace(accessKeyId) &&
            !string.IsNullOrWhiteSpace(secretAccessKey) &&
            !string.IsNullOrWhiteSpace(_r2BucketName))
        {
            AWSConfigsS3.UseSignatureVersion4 = true;
            _s3Client = new AmazonS3Client(
                accessKeyId,
                secretAccessKey,
                new AmazonS3Config
                {
                    ServiceURL = $"https://{accountId}.r2.cloudflarestorage.com",
                    SignatureVersion = "4"
                });
            _logger.LogInformation("R2 storage configured: bucket={Bucket}", _r2BucketName);
        }

        _logger.LogInformation("MediaFileService initialized: OS={Os}, {MappingCount} path mappings, {SearchPathCount} search paths, R2={R2}",
            _isWindows ? "Windows" : "Linux", _pathMappings.Count, _searchPaths.Count, _s3Client != null ? "enabled" : "disabled");
    }

    public bool IsConfigured => _pathMappings.Count > 0 || _searchPaths.Count > 0;

    public IReadOnlyList<string> SearchPaths => _searchPaths.AsReadOnly();

    public string? FindMedia(string? storedPath)
    {
        if (string.IsNullOrEmpty(storedPath))
            return null;

        // R2-only paths (e.g. "DataSet_1/..." or "NATIVES/...") are not local files — skip disk search
        if (storedPath.StartsWith("DataSet_", StringComparison.OrdinalIgnoreCase) ||
            storedPath.StartsWith("NATIVES/", StringComparison.OrdinalIgnoreCase))
            return null;

        // 1. Try direct path (works when running on same OS as DB was created)
        if (File.Exists(storedPath))
            return storedPath;

        // 2. Try path prefix translation (primary strategy)
        var translated = TranslatePath(storedPath);
        if (translated != null)
        {
            if (File.Exists(translated))
            {
                _logger.LogDebug("Resolved via path mapping: {Stored} -> {Local}", storedPath, translated);
                return translated;
            }
            // Mapping matched but file not on disk - skip expensive fallback search
            _logger.LogDebug("Path mapped but file not on disk: {Translated}", translated);
            return null;
        }

        // 3. Fallback: search by filename only when no mapping matched
        var fileName = Path.GetFileName(storedPath);
        if (string.IsNullOrEmpty(fileName))
            return null;

        var eftaNumber = ExtractEftaNumber(storedPath);
        var found = SearchInPaths(eftaNumber, fileName);
        if (found != null)
            _logger.LogDebug("Resolved via search fallback: {Stored} -> {Local}", storedPath, found);
        else
            _logger.LogDebug("Media file not found: {Path}", storedPath);

        return found;
    }

    public string? GetR2Url(string? storedPath)
    {
        if (_s3Client == null || string.IsNullOrEmpty(storedPath))
            return null;

        string objectKey;

        // Direct R2 key paths: "DataSet_..." or "NATIVES/..."
        // e.g. "DataSet_1/IMAGES/0001/EFTA00000002_p1_img1.png"
        // e.g. "NATIVES/0001/EFTA01683546.wav"
        if (storedPath.StartsWith("DataSet_", StringComparison.OrdinalIgnoreCase) ||
            storedPath.StartsWith("NATIVES/", StringComparison.OrdinalIgnoreCase))
        {
            objectKey = storedPath.Replace('\\', '/');
        }
        else
        {
            // Legacy format: build key as extracted_images/{EFTA}/{filename}
            var eftaNumber = ExtractEftaNumber(storedPath);
            var fileName = Path.GetFileName(storedPath);
            if (string.IsNullOrEmpty(eftaNumber) || string.IsNullOrEmpty(fileName))
                return null;

            objectKey = $"extracted_images/{eftaNumber}/{fileName}";
        }

        var url = _s3Client.GetPreSignedURL(new GetPreSignedUrlRequest
        {
            BucketName = _r2BucketName,
            Key = objectKey,
            Expires = DateTime.UtcNow.AddHours(1),
            Verb = HttpVerb.GET,
            Protocol = Protocol.HTTPS
        });

        _logger.LogDebug("Generated R2 pre-signed URL for {Key}", objectKey);
        return url;
    }

    /// <summary>
    /// Translates a DB path to a local OS path using configured prefix mappings.
    /// DB paths are Linux format: /data/epstein_files/DataSet_10/0182/EFTA01748599.pdf
    /// Windows result:            D:\Personal\Epstein\data\files\DataSet_10\0182\EFTA01748599.pdf
    /// </summary>
    private string? TranslatePath(string dbPath)
    {
        foreach (var mapping in _pathMappings)
        {
            if (dbPath.StartsWith(mapping.DbPrefix, StringComparison.OrdinalIgnoreCase))
            {
                var relativePart = dbPath.Substring(mapping.DbPrefix.Length);

                // Convert path separators for the target OS
                if (_isWindows)
                    relativePart = relativePart.Replace('/', '\\');
                else
                    relativePart = relativePart.Replace('\\', '/');

                return mapping.LocalPrefix + relativePart;
            }
        }

        return null;
    }

    private string? SearchInPaths(string? eftaNumber, string fileName)
    {
        foreach (var searchPath in _searchPaths)
        {
            // Try EFTA-specific subdirectory first
            if (!string.IsNullOrEmpty(eftaNumber))
            {
                var eftaPath = Path.Combine(searchPath, eftaNumber, fileName);
                if (File.Exists(eftaPath))
                    return eftaPath;

                var extractedImagesPath = Path.Combine(searchPath, "extracted_images", eftaNumber, fileName);
                if (File.Exists(extractedImagesPath))
                    return extractedImagesPath;
            }

            // Try direct file in search path
            var directPath = Path.Combine(searchPath, fileName);
            if (File.Exists(directPath))
                return directPath;

            // Recursive search (limited depth for performance)
            try
            {
                var found = SearchDirectory(searchPath, fileName, maxDepth: 3);
                if (found != null)
                    return found;
            }
            catch (Exception ex)
            {
                _logger.LogDebug(ex, "Error searching directory {Path}", searchPath);
            }
        }

        return null;
    }

    private static string? ExtractEftaNumber(string path)
    {
        var segments = path.Split('/', '\\');
        foreach (var segment in segments)
        {
            if (segment.StartsWith("EFTA", StringComparison.OrdinalIgnoreCase) && segment.Length >= 8)
            {
                var underscoreIndex = segment.IndexOf('_');
                if (underscoreIndex > 0)
                    return segment.Substring(0, underscoreIndex);

                var dotIndex = segment.LastIndexOf('.');
                if (dotIndex > 0)
                    return segment.Substring(0, dotIndex);

                return segment;
            }
        }

        return null;
    }

    private string? SearchDirectory(string basePath, string fileName, int maxDepth)
    {
        if (maxDepth <= 0)
            return null;

        try
        {
            var filePath = Path.Combine(basePath, fileName);
            if (File.Exists(filePath))
                return filePath;

            foreach (var dir in Directory.EnumerateDirectories(basePath))
            {
                var result = SearchDirectory(dir, fileName, maxDepth - 1);
                if (result != null)
                    return result;
            }
        }
        catch (UnauthorizedAccessException) { }
        catch (DirectoryNotFoundException) { }

        return null;
    }

    private record PathMapping(string DbPrefix, string LocalPrefix);
}
