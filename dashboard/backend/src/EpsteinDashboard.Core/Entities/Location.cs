namespace EpsteinDashboard.Core.Entities;

public class Location
{
    public long LocationId { get; set; }
    public string LocationName { get; set; } = string.Empty;
    public string? LocationType { get; set; }
    public string? StreetAddress { get; set; }
    public string? City { get; set; }
    public string? StateProvince { get; set; }
    public string? Country { get; set; }
    public string? PostalCode { get; set; }
    public double? Latitude { get; set; }
    public double? Longitude { get; set; }
    public long? OwnerPersonId { get; set; }
    public long? OwnerOrganizationId { get; set; }
    public string? Description { get; set; }
    public long? FirstMentionedInDocId { get; set; }
    public string? CreatedAt { get; set; }
    public string? UpdatedAt { get; set; }

    // Navigation properties
    public Person? OwnerPerson { get; set; }
    public Organization? OwnerOrganization { get; set; }
    public Document? FirstMentionedInDocument { get; set; }
    public ICollection<Event> Events { get; set; } = new List<Event>();
    public ICollection<EvidenceItem> SeizedEvidenceItems { get; set; } = new List<EvidenceItem>();
    public ICollection<MediaFile> MediaFiles { get; set; } = new List<MediaFile>();
}
