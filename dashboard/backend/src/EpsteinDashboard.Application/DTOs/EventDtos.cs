namespace EpsteinDashboard.Application.DTOs;

public class EventDto
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
    public string? LocationName { get; set; }
    public string? ConfidenceLevel { get; set; }
    public string? VerificationStatus { get; set; }
    public string? CreatedAt { get; set; }
}

public class TimelineEventDto
{
    public long EventId { get; set; }
    public string? Title { get; set; }
    public string? EventDate { get; set; }
    public string? EndDate { get; set; }
    public string? EventType { get; set; }
    public string? Location { get; set; }
    public List<string> ParticipantNames { get; set; } = new();
}

public class EventParticipantDto
{
    public long ParticipantId { get; set; }
    public string? PersonName { get; set; }
    public string? OrganizationName { get; set; }
    public string? ParticipationRole { get; set; }
    public string? Notes { get; set; }
}
