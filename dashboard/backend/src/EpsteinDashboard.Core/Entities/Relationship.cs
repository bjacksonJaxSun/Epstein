namespace EpsteinDashboard.Core.Entities;

public class Relationship
{
    public long RelationshipId { get; set; }
    public long Person1Id { get; set; }
    public long Person2Id { get; set; }
    public string? RelationshipType { get; set; }
    public string? RelationshipDescription { get; set; }
    public string? StartDate { get; set; }
    public string? EndDate { get; set; }
    public bool? IsCurrent { get; set; }
    public long? SourceDocumentId { get; set; }
    public string? ConfidenceLevel { get; set; }
    public string? CreatedAt { get; set; }
    public string? UpdatedAt { get; set; }

    // Navigation properties
    public Person? Person1 { get; set; }
    public Person? Person2 { get; set; }
    public Document? SourceDocument { get; set; }
}
