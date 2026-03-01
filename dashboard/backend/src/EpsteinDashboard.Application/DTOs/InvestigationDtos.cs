namespace EpsteinDashboard.Application.DTOs;

/// <summary>
/// A single person-at-location entry for the geo timeline map view.
/// </summary>
public class GeoTimelineEntryDto
{
    public long PlacementId { get; set; }
    public long LocationId { get; set; }
    public string LocationName { get; set; } = string.Empty;
    public double? Latitude { get; set; }
    public double? Longitude { get; set; }
    public string? City { get; set; }
    public string? Country { get; set; }
    public string? LocationType { get; set; }
    public string PersonName { get; set; } = string.Empty;
    public long? PersonId { get; set; }
    public DateTime? PlacementDate { get; set; }
    public DateTime? DateEnd { get; set; }
    public string? ActivityType { get; set; }
    public string? Description { get; set; }
    public decimal? Confidence { get; set; }
}

/// <summary>
/// A location that a person has visited, with visit statistics.
/// </summary>
public class ConnectedLocationDto
{
    public long LocationId { get; set; }
    public string LocationName { get; set; } = string.Empty;
    public string? City { get; set; }
    public string? Country { get; set; }
    public double? Latitude { get; set; }
    public double? Longitude { get; set; }
    public int VisitCount { get; set; }
    public DateTime? FirstVisit { get; set; }
    public DateTime? LastVisit { get; set; }
    public string? MostRecentActivityType { get; set; }
}

/// <summary>
/// An event that a person participated in.
/// </summary>
public class ConnectedEventDto
{
    public long EventId { get; set; }
    public string? EventType { get; set; }
    public string? Title { get; set; }
    public DateTime? EventDate { get; set; }
    public string? LocationName { get; set; }
    public long? LocationId { get; set; }
    public string? ParticipationRole { get; set; }
}

/// <summary>
/// A financial transaction connected to a person.
/// </summary>
public class ConnectedFinancialDto
{
    public long TransactionId { get; set; }
    public string Direction { get; set; } = string.Empty; // "sent" or "received"
    public decimal? Amount { get; set; }
    public string? Currency { get; set; }
    public string? CounterpartyName { get; set; }
    public string? TransactionDate { get; set; }
    public string? Purpose { get; set; }
}

/// <summary>
/// A person connected to the subject via relationships or shared presence.
/// </summary>
public class ConnectedPersonDto
{
    public long PersonId { get; set; }
    public string PersonName { get; set; } = string.Empty;
    public string? RelationshipType { get; set; }
    public string? PrimaryRole { get; set; }
    public string? Source { get; set; } // "relationship", "co-location", "financial", "event"
    public int SharedCount { get; set; } // shared locations / transactions / events
}

/// <summary>
/// A co-presence instance: subject and another person at the same location around the same time.
/// </summary>
public class CoPresenceDto
{
    public string OtherPersonName { get; set; } = string.Empty;
    public long? OtherPersonId { get; set; }
    public long LocationId { get; set; }
    public string LocationName { get; set; } = string.Empty;
    public DateTime? SubjectDate { get; set; }
    public DateTime? OtherDate { get; set; }
    public string? ActivityType { get; set; }
    public int OverlapDays { get; set; }
}

/// <summary>
/// All connections for a specific person — drives the investigation side panel.
/// </summary>
public class PersonConnectionsDto
{
    public long PersonId { get; set; }
    public string PersonName { get; set; } = string.Empty;
    public string? PrimaryRole { get; set; }
    public string? EpsteinRelationship { get; set; }
    public List<ConnectedLocationDto> Locations { get; set; } = new();
    public List<ConnectedEventDto> Events { get; set; } = new();
    public List<ConnectedFinancialDto> FinancialTransactions { get; set; } = new();
    public List<ConnectedPersonDto> RelatedPeople { get; set; } = new();
    public List<CoPresenceDto> CoPresences { get; set; } = new();
}

/// <summary>
/// A location where multiple investigated persons were present — the "shared presence" view.
/// </summary>
public class SharedPresenceDto
{
    public long LocationId { get; set; }
    public string LocationName { get; set; } = string.Empty;
    public string? City { get; set; }
    public string? Country { get; set; }
    public double? Latitude { get; set; }
    public double? Longitude { get; set; }
    public int PersonCount { get; set; }
    public List<string> PersonNames { get; set; } = new();
    public DateTime? EarliestDate { get; set; }
    public DateTime? LatestDate { get; set; }
}

/// <summary>
/// A person search result for adding subjects to the investigation.
/// </summary>
public class PersonSearchResultDto
{
    public long PersonId { get; set; }
    public string PersonName { get; set; } = string.Empty;
    public string? PrimaryRole { get; set; }
    public string? EpsteinRelationship { get; set; }
    public int PlacementCount { get; set; }
    public int EventCount { get; set; }
}
