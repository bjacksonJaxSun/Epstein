using EpsteinDashboard.Core.Interfaces;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;

namespace EpsteinDashboard.Infrastructure.Services;

/// <summary>
/// Cross-platform media file location service.
/// Searches configured directories for media files extracted from documents.
/// </summary>
public class MediaFileService : IMediaFileService
{
    private readonly ILogger<MediaFileService> _logger;
    private readonly List<string> _searchPaths;

    public MediaFileService(IConfiguration configuration, ILogger<MediaFileService> logger)
    {
        _logger = logger;
        _searchPaths = new List<string>();

        // Load configuration from MediaFiles section
        var mediaConfig = configuration.GetSection("MediaFiles");

        // Get search paths array
        var pathsSection = mediaConfig.GetSection("SearchPaths");
        foreach (var child in pathsSection.GetChildren())
        {
            var path = child.Value;
            if (!string.IsNullOrWhiteSpace(path) && Directory.Exists(path))
            {
                _searchPaths.Add(path);
                _logger.LogInformation("Media search path configured: {Path}", path);
            }
            else if (!string.IsNullOrWhiteSpace(path))
            {
                _logger.LogWarning("Media search path does not exist: {Path}", path);
            }
        }

        if (_searchPaths.Count == 0)
        {
            _logger.LogWarning("No valid media search paths configured. Media file serving will be unavailable.");
        }
    }

    public bool IsConfigured => _searchPaths.Count > 0;

    public IReadOnlyList<string> SearchPaths => _searchPaths.AsReadOnly();

    public string? FindMedia(string? storedPath)
    {
        if (string.IsNullOrEmpty(storedPath))
            return null;

        // 1. Try stored path first (works when paths match current environment)
        if (File.Exists(storedPath))
        {
            _logger.LogDebug("Found media at stored path: {Path}", storedPath);
            return storedPath;
        }

        // 2. Extract filename from stored path
        var fileName = Path.GetFileName(storedPath);
        if (string.IsNullOrEmpty(fileName))
            return null;

        // 3. Extract EFTA number from path or filename
        var eftaNumber = ExtractEftaNumber(storedPath);

        // 4. Search in configured paths
        return SearchInPaths(eftaNumber, fileName);
    }

    private string? SearchInPaths(string? eftaNumber, string fileName)
    {
        foreach (var searchPath in _searchPaths)
        {
            // Try EFTA-specific subdirectory first (most common structure)
            // Pattern: /data/extraction_output/extracted_images/EFTA00068047/EFTA00068047_p1_img1.jpg
            if (!string.IsNullOrEmpty(eftaNumber))
            {
                var eftaPath = Path.Combine(searchPath, eftaNumber, fileName);
                if (File.Exists(eftaPath))
                {
                    _logger.LogDebug("Found media in EFTA directory: {Path}", eftaPath);
                    return eftaPath;
                }

                // Try extracted_images/EFTA subdirectory structure
                var extractedImagesPath = Path.Combine(searchPath, "extracted_images", eftaNumber, fileName);
                if (File.Exists(extractedImagesPath))
                {
                    _logger.LogDebug("Found media in extracted_images: {Path}", extractedImagesPath);
                    return extractedImagesPath;
                }
            }

            // Try direct file in search path
            var directPath = Path.Combine(searchPath, fileName);
            if (File.Exists(directPath))
            {
                _logger.LogDebug("Found media directly in search path: {Path}", directPath);
                return directPath;
            }

            // Try recursive search in subdirectories (limited depth for performance)
            try
            {
                var found = SearchDirectory(searchPath, fileName, maxDepth: 3);
                if (found != null)
                {
                    _logger.LogDebug("Found media via directory search: {Path}", found);
                    return found;
                }
            }
            catch (Exception ex)
            {
                _logger.LogDebug(ex, "Error searching directory {Path}", searchPath);
            }
        }

        _logger.LogDebug("Media file not found: {FileName}", fileName);
        return null;
    }

    private static string? ExtractEftaNumber(string path)
    {
        // Try to extract EFTA number from path segments or filename
        // Pattern: EFTA followed by digits (e.g., EFTA00068047)
        var segments = path.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

        foreach (var segment in segments)
        {
            if (segment.StartsWith("EFTA", StringComparison.OrdinalIgnoreCase) && segment.Length >= 8)
            {
                // Return just the EFTA number part (before any underscore suffix like _p1_img1)
                var underscoreIndex = segment.IndexOf('_');
                if (underscoreIndex > 0)
                    return segment.Substring(0, underscoreIndex);

                // Check if it ends with an extension
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
            // Check current directory
            var filePath = Path.Combine(basePath, fileName);
            if (File.Exists(filePath))
                return filePath;

            // Search subdirectories
            foreach (var dir in Directory.EnumerateDirectories(basePath))
            {
                var result = SearchDirectory(dir, fileName, maxDepth - 1);
                if (result != null)
                    return result;
            }
        }
        catch (UnauthorizedAccessException)
        {
            // Skip directories we can't access
        }
        catch (DirectoryNotFoundException)
        {
            // Directory was deleted while searching
        }

        return null;
    }
}
