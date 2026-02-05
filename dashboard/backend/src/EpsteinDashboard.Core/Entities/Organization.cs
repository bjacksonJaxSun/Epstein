namespace EpsteinDashboard.Core.Entities;

public class Organization
{
    public long OrganizationId { get; set; }
    public string OrganizationName { get; set; } = string.Empty;
    public string? OrganizationType { get; set; }
    public long? ParentOrganizationId { get; set; }
    public string? HeadquartersLocation { get; set; }
    public string? Website { get; set; }
    public string? Description { get; set; }
    public long? FirstMentionedInDocId { get; set; }
    public string? CreatedAt { get; set; }
    public string? UpdatedAt { get; set; }

    // Navigation properties
    public Organization? ParentOrganization { get; set; }
    public ICollection<Organization> ChildOrganizations { get; set; } = new List<Organization>();
    public Document? FirstMentionedInDocument { get; set; }
    public ICollection<Location> OwnedLocations { get; set; } = new List<Location>();
    public ICollection<EventParticipant> EventParticipations { get; set; } = new List<EventParticipant>();
    public ICollection<Communication> SentCommunications { get; set; } = new List<Communication>();
    public ICollection<CommunicationRecipient> ReceivedCommunications { get; set; } = new List<CommunicationRecipient>();
    public ICollection<FinancialTransaction> TransactionsAsFrom { get; set; } = new List<FinancialTransaction>();
    public ICollection<FinancialTransaction> TransactionsAsTo { get; set; } = new List<FinancialTransaction>();
}
