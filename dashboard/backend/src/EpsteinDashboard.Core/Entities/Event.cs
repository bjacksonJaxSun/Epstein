namespace EpsteinDashboard.Core.Entities;

public class Event
{
    public long EventId { get; set; }
    public string? EventType { get; set; }
    public string? Title { get; set; }
    public string? Description { get; set; }
    public string? EventDate { get; set; }
    public string? EventTime { get; set; }
    public string? EndDate { get; set; }
    public string? EndTime { get; set; }
    public int? DurationMinutes { get; set; }
    public long? LocationId { get; set; }
    public long? SourceDocumentId { get; set; }
    public string? AdditionalSourceDocs { get; set; } // JSON
    public string? ConfidenceLevel { get; set; }
    public string? VerificationStatus { get; set; }
    public string? Notes { get; set; }
    public string? CreatedAt { get; set; }
    public string? UpdatedAt { get; set; }

    // Navigation properties
    public Location? Location { get; set; }
    public Document? SourceDocument { get; set; }
    public ICollection<EventParticipant> Participants { get; set; } = new List<EventParticipant>();
    public ICollection<MediaEvent> MediaEvents { get; set; } = new List<MediaEvent>();
}
