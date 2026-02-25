namespace EpsteinDashboard.Core.Entities;

public class Communication
{
    public long CommunicationId { get; set; }
    public string? CommunicationType { get; set; }
    public long? SenderPersonId { get; set; }
    public long? SenderOrganizationId { get; set; }
    public string? Subject { get; set; }
    public string? BodyText { get; set; }
    public DateTime? CommunicationDate { get; set; }
    public string? CommunicationTime { get; set; }
    public long? SourceDocumentId { get; set; }
    public bool? HasAttachments { get; set; }
    public int? AttachmentCount { get; set; }
    public DateTime? CreatedAt { get; set; }
    public DateTime? UpdatedAt { get; set; }

    // Navigation properties
    public Person? SenderPerson { get; set; }
    public Organization? SenderOrganization { get; set; }
    public Document? SourceDocument { get; set; }
    public ICollection<CommunicationRecipient> Recipients { get; set; } = new List<CommunicationRecipient>();
}
