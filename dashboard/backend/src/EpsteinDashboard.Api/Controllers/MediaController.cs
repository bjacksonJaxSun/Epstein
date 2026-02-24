using System.Diagnostics;
using AutoMapper;
using EpsteinDashboard.Application.DTOs;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Microsoft.AspNetCore.Mvc;

namespace EpsteinDashboard.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class MediaController : ControllerBase
{
    private readonly IMediaRepository _repository;
    private readonly IMediaFileService _mediaFileService;
    private readonly IMapper _mapper;
    // Limit concurrent ffmpeg processes to avoid saturating R2 bandwidth
    private static readonly SemaphoreSlim ThumbnailSemaphore = new(2, 2);
    private static readonly string ThumbnailCacheDir = System.Runtime.InteropServices.RuntimeInformation
        .IsOSPlatform(System.Runtime.InteropServices.OSPlatform.Windows)
        ? Path.Combine(Path.GetTempPath(), "epstein_video_thumbnails")
        : "/data/video_thumbnails";
    private static readonly string FfmpegPath = ResolveFfmpeg();

    private static string ResolveFfmpeg()
    {
        // On Linux, just use "ffmpeg" from PATH
        if (!System.Runtime.InteropServices.RuntimeInformation.IsOSPlatform(
                System.Runtime.InteropServices.OSPlatform.Windows))
            return "ffmpeg";

        // Check common Windows locations
        var candidates = new[]
        {
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "Microsoft", "WinGet", "Links", "ffmpeg.exe"),
            @"C:\ffmpeg\bin\ffmpeg.exe",
            @"C:\tools\ffmpeg\bin\ffmpeg.exe",
            @"C:\ProgramData\chocolatey\bin\ffmpeg.exe",
        };

        foreach (var path in candidates)
        {
            if (System.IO.File.Exists(path))
                return path;
        }

        return "ffmpeg"; // fallback to PATH
    }

    public MediaController(IMediaRepository repository, IMediaFileService mediaFileService, IMapper mapper)
    {
        _repository = repository;
        _mediaFileService = mediaFileService;
        _mapper = mapper;

        // Ensure thumbnail cache directory exists
        if (!Directory.Exists(ThumbnailCacheDir))
        {
            Directory.CreateDirectory(ThumbnailCacheDir);
        }
    }

    [HttpGet]
    public async Task<ActionResult<PagedResult<MediaFileDto>>> GetMediaFiles(
        [FromQuery] int page = 0,
        [FromQuery] int pageSize = 50,
        [FromQuery] string? mediaType = null,
        [FromQuery] string? sortBy = null,
        [FromQuery] string? sortDirection = "asc",
        [FromQuery] bool excludeDocumentScans = false,
        CancellationToken cancellationToken = default)
    {
        var result = await _repository.GetFilteredAsync(page, pageSize, mediaType, sortBy, sortDirection, excludeDocumentScans, cancellationToken);
        return Ok(new PagedResult<MediaFileDto>
        {
            Items = _mapper.Map<IReadOnlyList<MediaFileDto>>(result.Items),
            TotalCount = result.TotalCount,
            Page = result.Page,
            PageSize = result.PageSize
        });
    }

    [HttpGet("{id:long}")]
    public async Task<ActionResult<MediaFileDto>> GetMediaFile(long id, CancellationToken cancellationToken)
    {
        // Use simple GetByIdAsync to avoid missing table errors
        var media = await _repository.GetByIdAsync(id, cancellationToken);
        if (media == null) return NotFound();
        return Ok(_mapper.Map<MediaFileDto>(media));
    }

    [HttpGet("find-by-name")]
    public async Task<ActionResult<MediaFileDto>> FindByFilename(
        [FromQuery] string filename,
        [FromQuery] string? mediaType = null,
        [FromQuery] bool excludeDocumentScans = false,
        CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(filename))
            return BadRequest("Filename is required");

        var media = await _repository.FindByFilenameAsync(filename.Trim(), mediaType, excludeDocumentScans, cancellationToken);
        if (media == null) return NotFound("No media file matching that filename");
        return Ok(_mapper.Map<MediaFileDto>(media));
    }

    [HttpGet("{id:long}/position")]
    public async Task<ActionResult<MediaPositionDto>> GetMediaPosition(
        long id,
        [FromQuery] int pageSize = 48,
        [FromQuery] string? mediaType = null,
        [FromQuery] bool excludeDocumentScans = false,
        CancellationToken cancellationToken = default)
    {
        var position = await _repository.GetMediaPositionAsync(id, pageSize, mediaType, excludeDocumentScans, cancellationToken);
        if (position == null) return NotFound();
        return Ok(new MediaPositionDto
        {
            MediaFileId = position.MediaFileId,
            Page = position.Page,
            IndexOnPage = position.IndexOnPage,
            GlobalIndex = position.GlobalIndex,
            TotalCount = position.TotalCount,
            TotalPages = position.TotalPages
        });
    }

    [HttpGet("{id:long}/analysis")]
    public async Task<ActionResult<IReadOnlyList<ImageAnalysisDto>>> GetAnalysis(long id, CancellationToken cancellationToken)
    {
        var analyses = await _repository.GetAnalysesForMediaAsync(id, cancellationToken);
        return Ok(_mapper.Map<IReadOnlyList<ImageAnalysisDto>>(analyses));
    }

    [HttpGet("{id:long}/nearest")]
    public async Task<ActionResult<object>> GetNearestMedia(
        long id,
        [FromQuery] string? mediaType = null,
        [FromQuery] bool excludeDocumentScans = false,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var (nearestId, isExactMatch) = await _repository.FindNearestAsync(id, mediaType, excludeDocumentScans, cancellationToken);
            return Ok(new { nearestId, isExactMatch });
        }
        catch (InvalidOperationException)
        {
            return NotFound("No media files found matching the current filters");
        }
    }

    [HttpGet("{id:long}/file")]
    public async Task<IActionResult> GetFile(long id, CancellationToken cancellationToken)
    {
        var media = await _repository.GetByIdAsync(id, cancellationToken);
        if (media == null) return NotFound();

        if (string.IsNullOrEmpty(media.FilePath))
            return NotFound("File path not available.");

        // Use IMediaFileService to resolve the actual file path
        var resolvedPath = _mediaFileService.FindMedia(media.FilePath);
        if (string.IsNullOrEmpty(resolvedPath) || !System.IO.File.Exists(resolvedPath))
        {
            // Fallback: try R2 pre-signed URL redirect
            var r2Url = _mediaFileService.GetR2Url(media.FilePath);
            if (r2Url != null)
                return Redirect(r2Url);
            return NotFound("File not found on disk.");
        }

        var contentType = media.MediaType?.ToLowerInvariant() switch
        {
            "image" => media.FileFormat?.ToLowerInvariant() switch
            {
                "jpg" or "jpeg" => "image/jpeg",
                "png" => "image/png",
                "gif" => "image/gif",
                "webp" => "image/webp",
                "bmp" => "image/bmp",
                "tiff" or "tif" => "image/tiff",
                _ => "application/octet-stream"
            },
            "video" => media.FileFormat?.ToLowerInvariant() switch
            {
                "mp4" or "m4v" => "video/mp4",
                "webm" => "video/webm",
                "avi" => "video/x-msvideo",
                "mov" => "video/quicktime",
                "wmv" => "video/x-ms-wmv",
                "mkv" => "video/x-matroska",
                _ => "video/mp4"
            },
            "audio" => media.FileFormat?.ToLowerInvariant() switch
            {
                "mp3" => "audio/mpeg",
                "wav" => "audio/wav",
                "ogg" => "audio/ogg",
                "m4a" or "aac" => "audio/aac",
                _ => "audio/mpeg"
            },
            "document" => "application/pdf",
            _ => "application/octet-stream"
        };

        // Use PhysicalFile to enable Range request support (required for video seeking/thumbnails)
        return PhysicalFile(resolvedPath, contentType, media.FileName ?? Path.GetFileName(resolvedPath), enableRangeProcessing: true);
    }

    [HttpGet("{id:long}/thumbnail")]
    public async Task<IActionResult> GetThumbnail(long id, CancellationToken cancellationToken)
    {
        var media = await _repository.GetByIdAsync(id, cancellationToken);
        if (media == null) return NotFound();

        // For images, return the image itself
        if (media.MediaType?.ToLowerInvariant() == "image")
        {
            if (string.IsNullOrEmpty(media.FilePath))
                return NotFound("File path not available.");

            var resolvedPath = _mediaFileService.FindMedia(media.FilePath);
            if (string.IsNullOrEmpty(resolvedPath) || !System.IO.File.Exists(resolvedPath))
            {
                var r2Url = _mediaFileService.GetR2Url(media.FilePath);
                if (r2Url != null)
                    return Redirect(r2Url);
                return NotFound("File not found on disk.");
            }

            return PhysicalFile(resolvedPath, "image/jpeg", enableRangeProcessing: true);
        }

        // For videos, generate/return cached thumbnail
        if (media.MediaType?.ToLowerInvariant() != "video")
            return NotFound("Thumbnails only available for images and videos.");

        if (string.IsNullOrEmpty(media.FilePath))
            return NotFound("Video file path not available.");

        // Resolve video source: local file or R2 URL
        var videoPath = _mediaFileService.FindMedia(media.FilePath);
        var isLocal = !string.IsNullOrEmpty(videoPath) && System.IO.File.Exists(videoPath);
        string? videoR2Url = null;

        if (!isLocal)
        {
            videoR2Url = _mediaFileService.GetR2Url(media.FilePath);
            if (videoR2Url == null)
                return NotFound("Video file not found on disk or R2.");
        }

        var ffmpegInput = isLocal ? videoPath! : videoR2Url!;
        var thumbnailPath = Path.Combine(ThumbnailCacheDir, $"{id}.jpg");

        // Return cached thumbnail if exists
        if (System.IO.File.Exists(thumbnailPath))
        {
            return PhysicalFile(thumbnailPath, "image/jpeg", enableRangeProcessing: true);
        }

        // Generate thumbnail using FFmpeg (works with both local files and URLs)
        // -ss BEFORE -i = input seeking (fast, no full download for HTTP sources)
        // Limit concurrency to avoid saturating R2 bandwidth with many ffmpeg processes
        if (!await ThumbnailSemaphore.WaitAsync(TimeSpan.FromSeconds(5), cancellationToken))
        {
            // Too many concurrent thumbnail requests - return 503 so browser retries later
            Response.Headers["Retry-After"] = "2";
            return StatusCode(503, "Thumbnail generation busy, retry shortly");
        }

        try
        {
            var timeoutMs = isLocal ? 15000 : 30000;

            var success = await RunFfmpegThumbnail(ffmpegInput, thumbnailPath, 1, timeoutMs, cancellationToken);

            if (!success)
                success = await RunFfmpegThumbnail(ffmpegInput, thumbnailPath, 0, timeoutMs, cancellationToken);

            if (System.IO.File.Exists(thumbnailPath))
            {
                return PhysicalFile(thumbnailPath, "image/jpeg", enableRangeProcessing: true);
            }

            return StatusCode(500, "Failed to generate thumbnail");
        }
        catch (Exception ex)
        {
            return StatusCode(500, $"Error generating thumbnail: {ex.Message}");
        }
        finally
        {
            ThumbnailSemaphore.Release();
        }
    }

    /// <summary>
    /// Returns information about media file service configuration.
    /// Useful for debugging path issues.
    /// </summary>
    [HttpGet("config")]
    public ActionResult GetMediaConfig()
    {
        return Ok(new
        {
            isConfigured = _mediaFileService.IsConfigured,
            searchPaths = _mediaFileService.SearchPaths
        });
    }

    private static async Task<bool> RunFfmpegThumbnail(string input, string outputPath, int seekSeconds, int timeoutMs, CancellationToken cancellationToken)
    {
        var process = new Process
        {
            StartInfo = new ProcessStartInfo
            {
                FileName = FfmpegPath,
                Arguments = $"-ss {seekSeconds} -i \"{input}\" -vframes 1 -vf \"scale=320:-1\" -update 1 -y \"{outputPath}\"",
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            }
        };

        process.Start();
        // Drain stdout/stderr to prevent pipe buffer deadlock
        var stderrTask = process.StandardError.ReadToEndAsync();
        var stdoutTask = process.StandardOutput.ReadToEndAsync();

        using var cts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        cts.CancelAfter(timeoutMs);
        try
        {
            await process.WaitForExitAsync(cts.Token);
        }
        catch (OperationCanceledException)
        {
            try { process.Kill(true); } catch { }
        }

        return process.ExitCode == 0 && System.IO.File.Exists(outputPath);
    }
}
