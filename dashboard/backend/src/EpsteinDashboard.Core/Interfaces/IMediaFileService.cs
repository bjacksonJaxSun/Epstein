namespace EpsteinDashboard.Core.Interfaces;

/// <summary>
/// Cross-platform media file location service.
/// Resolves media file paths using configurable search directories.
/// </summary>
public interface IMediaFileService
{
    /// <summary>
    /// Attempts to find a media file by its stored path, falling back to configured search paths.
    /// </summary>
    /// <param name="storedPath">The original path stored in the database</param>
    /// <returns>The resolved file path, or null if not found</returns>
    string? FindMedia(string? storedPath);

    /// <summary>
    /// Indicates whether the service is properly configured with search paths.
    /// </summary>
    bool IsConfigured { get; }

    /// <summary>
    /// Gets the configured search paths for media files.
    /// </summary>
    IReadOnlyList<string> SearchPaths { get; }

    /// <summary>
    /// Returns a pre-signed R2 URL for a media file, or null if R2 is not configured
    /// or the path cannot be mapped to an R2 key.
    /// </summary>
    string? GetR2Url(string? storedPath);
}
