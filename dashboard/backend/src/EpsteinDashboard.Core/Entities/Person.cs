namespace EpsteinDashboard.Core.Entities;

public class Person
{
    public long PersonId { get; set; }
    public string FullName { get; set; } = string.Empty;
    public string? NameVariations { get; set; } // JSON
    public string? PrimaryRole { get; set; }
    public string? Roles { get; set; } // JSON
    public string? EmailAddresses { get; set; } // JSON
    public string? PhoneNumbers { get; set; } // JSON
    public string? Addresses { get; set; } // JSON
    public bool? IsRedacted { get; set; }
    public string? VictimIdentifier { get; set; }
    public string? DateOfBirth { get; set; }
    public string? Nationality { get; set; }
    public string? Occupation { get; set; }
    public long? FirstMentionedInDocId { get; set; }
    public string? ConfidenceLevel { get; set; }
    public string? Notes { get; set; }
    public DateTime? CreatedAt { get; set; }
    public DateTime? UpdatedAt { get; set; }

    // Navigation properties
    public Document? FirstMentionedInDocument { get; set; }
    public ICollection<Relationship> RelationshipsAsPerson1 { get; set; } = new List<Relationship>();
    public ICollection<Relationship> RelationshipsAsPerson2 { get; set; } = new List<Relationship>();
    public ICollection<EventParticipant> EventParticipations { get; set; } = new List<EventParticipant>();
    public ICollection<Communication> SentCommunications { get; set; } = new List<Communication>();
    public ICollection<CommunicationRecipient> ReceivedCommunications { get; set; } = new List<CommunicationRecipient>();
    public ICollection<FinancialTransaction> TransactionsAsFrom { get; set; } = new List<FinancialTransaction>();
    public ICollection<FinancialTransaction> TransactionsAsTo { get; set; } = new List<FinancialTransaction>();
    public ICollection<Location> OwnedLocations { get; set; } = new List<Location>();
    public ICollection<EvidenceItem> SeizedFromItems { get; set; } = new List<EvidenceItem>();
    public ICollection<MediaPerson> MediaAppearances { get; set; } = new List<MediaPerson>();
    public ICollection<VisualEntity> VisualIdentifications { get; set; } = new List<VisualEntity>();
    public ICollection<DocumentPerson> DocumentMentions { get; set; } = new List<DocumentPerson>();
}
