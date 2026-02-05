namespace EpsteinDashboard.Application.DTOs;

public class PersonDto
{
    public long PersonId { get; set; }
    public string FullName { get; set; } = string.Empty;
    public string? PrimaryRole { get; set; }
    public string? Occupation { get; set; }
    public string? Nationality { get; set; }
    public string? ConfidenceLevel { get; set; }
    public bool? IsRedacted { get; set; }
    public string? CreatedAt { get; set; }
}

public class PersonListDto
{
    public long PersonId { get; set; }
    public string FullName { get; set; } = string.Empty;
    public string? PrimaryRole { get; set; }
    public string? Occupation { get; set; }
    public string? ConfidenceLevel { get; set; }
}

public class PersonDetailDto
{
    public long PersonId { get; set; }
    public string FullName { get; set; } = string.Empty;
    public string? NameVariations { get; set; }
    public string? PrimaryRole { get; set; }
    public string? Roles { get; set; }
    public string? EmailAddresses { get; set; }
    public string? PhoneNumbers { get; set; }
    public string? Addresses { get; set; }
    public bool? IsRedacted { get; set; }
    public string? VictimIdentifier { get; set; }
    public string? DateOfBirth { get; set; }
    public string? Nationality { get; set; }
    public string? Occupation { get; set; }
    public string? ConfidenceLevel { get; set; }
    public string? Notes { get; set; }
    public string? CreatedAt { get; set; }
    public string? UpdatedAt { get; set; }
    public List<RelationshipDto> Relationships { get; set; } = new();
}
