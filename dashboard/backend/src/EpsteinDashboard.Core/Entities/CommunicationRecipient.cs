namespace EpsteinDashboard.Core.Entities;

public class CommunicationRecipient
{
    public long CommunicationRecipientId { get; set; }
    public long CommunicationId { get; set; }
    public long? PersonId { get; set; }
    public long? OrganizationId { get; set; }
    public string? RecipientType { get; set; }
    public string? CreatedAt { get; set; }

    // Navigation properties
    public Communication? Communication { get; set; }
    public Person? Person { get; set; }
    public Organization? Organization { get; set; }
}
