namespace EpsteinDashboard.Core.Entities;

public class VisualEntity
{
    public long EntityId { get; set; }
    public long MediaFileId { get; set; }
    public string? EntityType { get; set; }
    public string? EntityLabel { get; set; }
    public string? EntityDescription { get; set; }
    public double? BboxX { get; set; }
    public double? BboxY { get; set; }
    public double? BboxWidth { get; set; }
    public double? BboxHeight { get; set; }
    public double? Confidence { get; set; }
    public long? PersonId { get; set; }
    public string? EstimatedAgeRange { get; set; }
    public string? Gender { get; set; }
    public string? FacialExpression { get; set; }
    public string? FaceEncoding { get; set; }
    public string? Attributes { get; set; } // JSON
    public DateTime? CreatedAt { get; set; }

    // Navigation properties
    public MediaFile? MediaFile { get; set; }
    public Person? Person { get; set; }
    public ICollection<MediaPerson> MediaPersonLinks { get; set; } = new List<MediaPerson>();
}
