namespace EpsteinDashboard.Core.Entities;

public class MediaPerson
{
    public long MediaPersonId { get; set; }
    public long MediaFileId { get; set; }
    public long PersonId { get; set; }
    public long? VisualEntityId { get; set; }
    public string? IdentificationMethod { get; set; }
    public double? Confidence { get; set; }
    public string? PositionDescription { get; set; }
    public string? Notes { get; set; }
    public string? TaggedBy { get; set; }
    public bool? Verified { get; set; }
    public string? VerifiedBy { get; set; }
    public string? VerifiedDate { get; set; }
    public DateTime? CreatedAt { get; set; }
    public DateTime? UpdatedAt { get; set; }

    // Navigation properties
    public MediaFile? MediaFile { get; set; }
    public Person? Person { get; set; }
    public VisualEntity? VisualEntity { get; set; }
}
