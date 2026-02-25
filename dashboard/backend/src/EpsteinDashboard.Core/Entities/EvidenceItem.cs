namespace EpsteinDashboard.Core.Entities;

public class EvidenceItem
{
    public long EvidenceId { get; set; }
    public string? EvidenceType { get; set; }
    public string? Description { get; set; }
    public string? EvidenceNumber { get; set; }
    public string? ChainOfCustody { get; set; }
    public long? SeizedFromLocationId { get; set; }
    public long? SeizedFromPersonId { get; set; }
    public string? SeizureDate { get; set; }
    public string? CurrentLocation { get; set; }
    public string? Status { get; set; }
    public long? SourceDocumentId { get; set; }
    public DateTime? CreatedAt { get; set; }
    public DateTime? UpdatedAt { get; set; }

    // Navigation properties
    public Location? SeizedFromLocation { get; set; }
    public Person? SeizedFromPerson { get; set; }
    public Document? SourceDocument { get; set; }
    public ICollection<MediaFile> MediaFiles { get; set; } = new List<MediaFile>();
}
