namespace EpsteinDashboard.Core.Entities;

public class MediaEvent
{
    public long MediaEventId { get; set; }
    public long MediaFileId { get; set; }
    public long EventId { get; set; }
    public bool? IsPrimaryEvidence { get; set; }
    public int? SequenceNumber { get; set; }
    public string? RelationshipDescription { get; set; }
    public string? CreatedAt { get; set; }
    public string? UpdatedAt { get; set; }

    // Navigation properties
    public MediaFile? MediaFile { get; set; }
    public Event? Event { get; set; }
}
