namespace EpsteinDashboard.Application.DTOs;

/// <summary>
/// Represents a person's placement at a location with evidence.
/// </summary>
public class LocationPlacementDto
{
    public long PlacementId { get; set; }

    // Person information
    public long? PersonId { get; set; }
    public string PersonName { get; set; } = string.Empty;

    // Date/time information
    public DateTime? PlacementDate { get; set; }
    public DateTime? DateEnd { get; set; }
    public string? DatePrecision { get; set; }  // exact, month, year, decade, season, unknown

    // Activity information
    public string? ActivityType { get; set; }   // visit, meeting, party, dinner, residence, flight, presence
    public string? Description { get; set; }

    // Evidence/source information
    public List<long> SourceDocumentIds { get; set; } = new();
    public List<string> SourceEftaNumbers { get; set; } = new();
    public List<string> EvidenceExcerpts { get; set; } = new();

    // Confidence
    public decimal? Confidence { get; set; }
    public string? ExtractionMethod { get; set; }
}

/// <summary>
/// Summary of placements at a location, grouped for UI display.
/// </summary>
public class LocationPlacementSummaryDto
{
    public long LocationId { get; set; }
    public string LocationName { get; set; } = string.Empty;

    // Aggregate counts
    public int TotalPlacements { get; set; }
    public int UniquePeopleCount { get; set; }
    public int DocumentCount { get; set; }

    // Date range
    public DateTime? EarliestDate { get; set; }
    public DateTime? LatestDate { get; set; }

    // List of placements
    public List<LocationPlacementDto> Placements { get; set; } = new();
}
