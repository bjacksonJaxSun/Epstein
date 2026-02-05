namespace EpsteinDashboard.Application.DTOs;

public class MediaFileDto
{
    public long MediaFileId { get; set; }
    public string? FilePath { get; set; }
    public string? FileName { get; set; }
    public string? MediaType { get; set; }
    public string? FileFormat { get; set; }
    public long? FileSizeBytes { get; set; }
    public string? DateTaken { get; set; }
    public double? GpsLatitude { get; set; }
    public double? GpsLongitude { get; set; }
    public int? WidthPixels { get; set; }
    public int? HeightPixels { get; set; }
    public double? DurationSeconds { get; set; }
    public string? Caption { get; set; }
    public bool? IsExplicit { get; set; }
    public bool? IsSensitive { get; set; }
    public string? ClassificationLevel { get; set; }
    public string? CreatedAt { get; set; }
}

public class ImageAnalysisDto
{
    public long AnalysisId { get; set; }
    public long MediaFileId { get; set; }
    public string? Description { get; set; }
    public string? GeneratedCaption { get; set; }
    public string? Tags { get; set; }
    public string? Categories { get; set; }
    public string? AnalysisProvider { get; set; }
    public double? ConfidenceScore { get; set; }
    public bool? ContainsText { get; set; }
    public string? ExtractedText { get; set; }
    public bool? ContainsFaces { get; set; }
    public int? FaceCount { get; set; }
    public string? SceneType { get; set; }
    public string? CreatedAt { get; set; }
}
