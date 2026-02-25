namespace EpsteinDashboard.Core.Entities;

public class EventParticipant
{
    public long ParticipantId { get; set; }
    public long EventId { get; set; }
    public long? PersonId { get; set; }
    public long? OrganizationId { get; set; }
    public string? ParticipationRole { get; set; }
    public string? Notes { get; set; }
    public DateTime? CreatedAt { get; set; }

    // Navigation properties
    public Event? Event { get; set; }
    public Person? Person { get; set; }
    public Organization? Organization { get; set; }
}
