namespace EpsteinDashboard.Core.Models;

/// <summary>
/// Represents a search result at the chunk level.
/// </summary>
public class ChunkSearchResult
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
/// Request for chunk-level search.
/// </summary>
public class ChunkSearchRequest
{
    public string Query { get; set; } = string.Empty;
    public int Page { get; set; } = 0;
    public int PageSize { get; set; } = 20;
    public string? DateFrom { get; set; }
    public string? DateTo { get; set; }
    public List<string>? DocumentTypes { get; set; }
    public bool IncludeContext { get; set; } = true;
    public bool UseVectorSearch { get; set; } = false;
    public int? MaxChunksPerDocument { get; set; }
}
