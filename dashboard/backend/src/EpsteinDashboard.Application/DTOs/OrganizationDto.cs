namespace EpsteinDashboard.Application.DTOs;

public class OrganizationDto
{
    public long OrganizationId { get; set; }
    public string OrganizationName { get; set; } = string.Empty;
    public string? OrganizationType { get; set; }
    public long? ParentOrganizationId { get; set; }
    public string? ParentOrganizationName { get; set; }
    public string? HeadquartersLocation { get; set; }
    public string? Website { get; set; }
    public string? Description { get; set; }
    public string? CreatedAt { get; set; }
    public string? UpdatedAt { get; set; }
}
