using EpsteinDashboard.Core.Models;

namespace EpsteinDashboard.Core.Interfaces;

/// <summary>
/// Service for searching document chunks with context preservation.
/// </summary>
public interface IChunkSearchService
{
    /// <summary>
    /// Search document chunks using FTS5 or vector similarity.
    /// </summary>
    Task<PagedResult<ChunkSearchResult>> SearchChunksAsync(
        ChunkSearchRequest request,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Get chunks for a specific document.
    /// </summary>
    Task<IReadOnlyList<ChunkSearchResult>> GetDocumentChunksAsync(
        long documentId,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Check if chunk search is available (chunks table exists).
    /// </summary>
    Task<bool> IsAvailableAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Get chunk search statistics.
    /// </summary>
    Task<ChunkSearchStats> GetStatsAsync(CancellationToken cancellationToken = default);
}

/// <summary>
/// Statistics about chunk search availability and coverage.
/// </summary>
public class ChunkSearchStats
{
    public long TotalDocuments { get; set; }
    public long DocumentsWithChunks { get; set; }
    public long TotalChunks { get; set; }
    public long ChunksWithEmbeddings { get; set; }
    public double AverageChunksPerDocument { get; set; }
    public bool FtsAvailable { get; set; }
    public bool VectorSearchAvailable { get; set; }
}
