namespace EpsteinDashboard.Core.Entities;

public class DocumentPerson
{
    public long Id { get; set; }
    public long DocumentId { get; set; }
    public long PersonId { get; set; }
    public int? MentionCount { get; set; }
    public string? MentionContext { get; set; }
    public string? RoleInDocument { get; set; }
    public double? Confidence { get; set; }
    public DateTime? CreatedAt { get; set; }

    // Navigation properties
    public Document? Document { get; set; }
    public Person? Person { get; set; }
}
