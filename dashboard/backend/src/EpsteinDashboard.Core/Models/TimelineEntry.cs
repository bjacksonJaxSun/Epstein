namespace EpsteinDashboard.Core.Models;

public class TimelineEntry
{
    public long EventId { get; set; }
    public string? Title { get; set; }
    public string? EventDate { get; set; }
    public string? EndDate { get; set; }
    public string? EventType { get; set; }
    public string? Location { get; set; }
    public List<string> ParticipantNames { get; set; } = new();
}
