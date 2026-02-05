namespace EpsteinDashboard.Application.DTOs;

public class DocumentDto
{
    public long DocumentId { get; set; }
    public string? EftaNumber { get; set; }
    public string? FilePath { get; set; }
    public string? DocumentType { get; set; }
    public string? DocumentDate { get; set; }
    public string? DocumentTitle { get; set; }
    public string? Author { get; set; }
    public string? Recipient { get; set; }
    public string? Subject { get; set; }
    public string? FullText { get; set; }
    public int? PageCount { get; set; }
    public long? FileSizeBytes { get; set; }
    public string? ClassificationLevel { get; set; }
    public bool? IsRedacted { get; set; }
    public string? RedactionLevel { get; set; }
    public string? SourceAgency { get; set; }
    public string? ExtractionStatus { get; set; }
    public double? ExtractionConfidence { get; set; }
    public string? CreatedAt { get; set; }
    public string? UpdatedAt { get; set; }
}

public class DocumentListDto
{
    public long DocumentId { get; set; }
    public string? EftaNumber { get; set; }
    public string? DocumentType { get; set; }
    public string? DocumentDate { get; set; }
    public string? DocumentTitle { get; set; }
    public string? Author { get; set; }
    public string? Subject { get; set; }
    public int? PageCount { get; set; }
    public string? ExtractionStatus { get; set; }
}
