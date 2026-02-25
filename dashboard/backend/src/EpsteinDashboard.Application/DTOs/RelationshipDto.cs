namespace EpsteinDashboard.Application.DTOs;

public class RelationshipDto
{
    public long RelationshipId { get; set; }
    public long Person1Id { get; set; }
    public string? Person1Name { get; set; }
    public long Person2Id { get; set; }
    public string? Person2Name { get; set; }
    public string? RelationshipType { get; set; }
    public string? RelationshipDescription { get; set; }
    public DateTime? StartDate { get; set; }
    public DateTime? EndDate { get; set; }
    public bool? IsCurrent { get; set; }
    public string? ConfidenceLevel { get; set; }
    public DateTime? CreatedAt { get; set; }
}
