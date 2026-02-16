namespace EpsteinDashboard.Core.Entities;

public class MediaFile
{
    public long MediaFileId { get; set; }
    public string? FilePath { get; set; }
    public string? FileName { get; set; }
    public string? MediaType { get; set; }
    public string? FileFormat { get; set; }
    public long? FileSizeBytes { get; set; }
    public string? Checksum { get; set; }
    public string? DateTaken { get; set; }
    public string? CameraMake { get; set; }
    public string? CameraModel { get; set; }
    public double? GpsLatitude { get; set; }
    public double? GpsLongitude { get; set; }
    public double? GpsAltitude { get; set; }
    public int? WidthPixels { get; set; }
    public int? HeightPixels { get; set; }
    public double? DurationSeconds { get; set; }
    public string? Orientation { get; set; }
    public string? OriginalFilename { get; set; }
    public string? Caption { get; set; }
    public long? SourceDocumentId { get; set; }
    public long? EvidenceItemId { get; set; }
    public long? LocationId { get; set; }
    public bool? IsExplicit { get; set; }
    public bool? IsSensitive { get; set; }
    public string? ClassificationLevel { get; set; }
    public bool? IsLikelyPhoto { get; set; }
    public string? CreatedAt { get; set; }
    public string? UpdatedAt { get; set; }

    // Navigation properties
    public Document? SourceDocument { get; set; }
    public EvidenceItem? EvidenceItem { get; set; }
    public Location? Location { get; set; }
    public ICollection<MediaPerson> TaggedPersons { get; set; } = new List<MediaPerson>();
    public ICollection<MediaEvent> MediaEvents { get; set; } = new List<MediaEvent>();
    public ICollection<VisualEntity> VisualEntities { get; set; } = new List<VisualEntity>();
    public ICollection<ImageAnalysis> Analyses { get; set; } = new List<ImageAnalysis>();
    public ICollection<ExtractionLog> ExtractionLogs { get; set; } = new List<ExtractionLog>();
}
