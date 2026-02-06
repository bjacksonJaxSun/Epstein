namespace EpsteinDashboard.Application.DTOs;

/// <summary>
/// DTO for chunk-level search results.
/// </summary>
public class ChunkSearchResultDto
{
    public string ChunkId { get; set; } = string.Empty;
    public long DocumentId { get; set; }
    public string? EftaNumber { get; set; }
    public int ChunkIndex { get; set; }
    public string? ChunkText { get; set; }
    public string? Snippet { get; set; }
    public int? PageNumber { get; set; }
    public bool HasRedaction { get; set; }
    public string? PrecedingContext { get; set; }
    public string? FollowingContext { get; set; }
    public double RelevanceScore { get; set; }

    // Parent document info
    public string? DocumentTitle { get; set; }
    public string? DocumentDate { get; set; }
    public string? DocumentType { get; set; }
}

/// <summary>
/// DTO for chunk search statistics.
/// </summary>
public class ChunkSearchStatsDto
{
    public long TotalDocuments { get; set; }
    public long DocumentsWithChunks { get; set; }
    public long TotalChunks { get; set; }
    public long ChunksWithEmbeddings { get; set; }
    public double AverageChunksPerDocument { get; set; }
    public bool FtsAvailable { get; set; }
    public bool VectorSearchAvailable { get; set; }
}
