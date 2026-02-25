namespace EpsteinDashboard.Core.Entities;

public class Relationship
{
    public long RelationshipId { get; set; }
    public long Person1Id { get; set; }
    public long Person2Id { get; set; }
    public string? RelationshipType { get; set; }
    public string? RelationshipDescription { get; set; }
    public DateTime? StartDate { get; set; }
    public DateTime? EndDate { get; set; }
    public bool? IsCurrent { get; set; }
    public long? SourceDocumentId { get; set; }
    public string? ConfidenceLevel { get; set; }
    public DateTime? CreatedAt { get; set; }
    public DateTime? UpdatedAt { get; set; }

    // Navigation properties
    public Person? Person1 { get; set; }
    public Person? Person2 { get; set; }
    public Document? SourceDocument { get; set; }
}
