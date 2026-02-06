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
    public string? Nationality { get; set; }
    public string? ConfidenceLevel { get; set; }
    public int DocumentCount { get; set; }
    public int EventCount { get; set; }
    public int RelationshipCount { get; set; }
    public int FinancialCount { get; set; }
    public int TotalMentions { get; set; }
    public string? EpsteinRelationship { get; set; }
}

public class DuplicateGroupDto
{
    public string CanonicalName { get; set; } = string.Empty;
    public List<PersonListDto> Variants { get; set; } = new();
    public int TotalDocuments { get; set; }
    public int TotalEvents { get; set; }
    public int TotalRelationships { get; set; }
}

public class MergePersonsRequest
{
    public long PrimaryPersonId { get; set; }
    public List<long> MergePersonIds { get; set; } = new();
}

public class PersonDetailDto
{
    public long PersonId { get; set; }
    public string FullName { get; set; } = string.Empty;
    public List<string>? NameVariations { get; set; }
    public string? PrimaryRole { get; set; }
    public List<string>? Roles { get; set; }
    public List<string>? EmailAddresses { get; set; }
    public List<string>? PhoneNumbers { get; set; }
    public List<string>? Addresses { get; set; }
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

    // Counts for related entities
    public int RelationshipCount { get; set; }
    public int EventCount { get; set; }
    public int DocumentCount { get; set; }
    public int FinancialTransactionCount { get; set; }
    public int MediaCount { get; set; }
}

public class EntityFrequencyDto
{
    public long Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public string EntityType { get; set; } = "person"; // person, organization
    public string? PrimaryRole { get; set; }
    public int DocumentCount { get; set; }
    public int EventCount { get; set; }
    public int RelationshipCount { get; set; }
    public int FinancialCount { get; set; }
    public decimal FinancialTotal { get; set; }
    public int MediaCount { get; set; }
    public int TotalMentions { get; set; } // Sum of all counts
}
