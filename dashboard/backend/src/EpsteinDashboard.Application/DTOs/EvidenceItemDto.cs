namespace EpsteinDashboard.Application.DTOs;

public class EvidenceItemDto
{
    public long EvidenceId { get; set; }
    public string? EvidenceType { get; set; }
    public string? Description { get; set; }
    public string? EvidenceNumber { get; set; }
    public string? ChainOfCustody { get; set; }
    public string? SeizedFromLocationName { get; set; }
    public string? SeizedFromPersonName { get; set; }
    public string? SeizureDate { get; set; }
    public string? CurrentLocation { get; set; }
    public string? Status { get; set; }
    public string? CreatedAt { get; set; }
}
