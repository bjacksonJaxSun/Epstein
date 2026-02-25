namespace EpsteinDashboard.Core.Entities;

public class ImageAnalysis
{
    public long AnalysisId { get; set; }
    public long MediaFileId { get; set; }
    public string? Description { get; set; }
    public string? GeneratedCaption { get; set; }
    public string? Tags { get; set; } // JSON
    public string? Categories { get; set; } // JSON
    public string? AnalysisProvider { get; set; }
    public string? AnalysisModelVersion { get; set; }
    public string? AnalysisDate { get; set; }
    public double? ConfidenceScore { get; set; }
    public bool? ContainsText { get; set; }
    public string? ExtractedText { get; set; }
    public string? TextLanguage { get; set; }
    public bool? ContainsFaces { get; set; }
    public int? FaceCount { get; set; }
    public string? SceneType { get; set; }
    public bool? IsExplicit { get; set; }
    public bool? IsSensitive { get; set; }
    public string? ModerationLabels { get; set; } // JSON
    public string? DominantColors { get; set; } // JSON
    public DateTime? CreatedAt { get; set; }
    public DateTime? UpdatedAt { get; set; }

    // Navigation properties
    public MediaFile? MediaFile { get; set; }
}
