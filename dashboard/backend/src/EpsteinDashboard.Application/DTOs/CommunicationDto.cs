namespace EpsteinDashboard.Application.DTOs;

public class CommunicationDto
{
    public long CommunicationId { get; set; }
    public string? CommunicationType { get; set; }
    public string? SenderName { get; set; }
    public string? Subject { get; set; }
    public string? BodyText { get; set; }
    public string? CommunicationDate { get; set; }
    public string? CommunicationTime { get; set; }
    public bool? HasAttachments { get; set; }
    public int? AttachmentCount { get; set; }
    public string? CreatedAt { get; set; }
    public List<CommunicationRecipientDto> Recipients { get; set; } = new();
}

public class CommunicationRecipientDto
{
    public long CommunicationRecipientId { get; set; }
    public string? PersonName { get; set; }
    public string? OrganizationName { get; set; }
    public string? RecipientType { get; set; }
}
