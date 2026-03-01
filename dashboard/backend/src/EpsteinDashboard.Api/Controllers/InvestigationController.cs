using Dapper;
using EpsteinDashboard.Application.DTOs;
using EpsteinDashboard.Infrastructure.Data;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace EpsteinDashboard.Api.Controllers;

/// <summary>
/// Investigation Workbench API — cross-entity queries for investigative analysis.
/// Ties together people, locations, events, and financial data.
/// </summary>
[ApiController]
[Route("api/[controller]")]
public class InvestigationController : ControllerBase
{
    private readonly EpsteinDbContext _context;

    public InvestigationController(EpsteinDbContext context)
    {
        _context = context;
    }

    /// <summary>
    /// Search for people to add as investigation subjects.
    /// </summary>
    [HttpGet("people/search")]
    public async Task<ActionResult<IReadOnlyList<PersonSearchResultDto>>> SearchPeople(
        [FromQuery] string q = "",
        [FromQuery] int limit = 20,
        CancellationToken cancellationToken = default)
    {
        var conn = _context.Database.GetDbConnection();
        // Use pre-aggregated subqueries to avoid massive cross-join between placements and events.
        // Joining both tables directly creates a cartesian product per person (e.g. 740 × 6027 rows for Epstein).
        const string sql = """
            SELECT
                p.person_id       AS PersonId,
                p.full_name       AS PersonName,
                p.primary_role    AS PrimaryRole,
                p.epstein_relationship AS EpsteinRelationship,
                COALESCE(plp.PlacementCount, 0) AS PlacementCount,
                COALESCE(ep.EventCount, 0)      AS EventCount
            FROM people p
            LEFT JOIN (
                SELECT person_id, COUNT(*) AS PlacementCount
                FROM person_location_placements
                GROUP BY person_id
            ) plp ON plp.person_id = p.person_id
            LEFT JOIN (
                SELECT person_id, COUNT(*) AS EventCount
                FROM event_participants
                GROUP BY person_id
            ) ep ON ep.person_id = p.person_id
            WHERE p.full_name ILIKE @Query
            ORDER BY COALESCE(plp.PlacementCount, 0) DESC, p.full_name
            LIMIT @Limit
            """;

        var results = await conn.QueryAsync<PersonSearchResultDto>(
            sql, new { Query = $"%{q}%", Limit = limit });
        return Ok(results.ToList());
    }

    /// <summary>
    /// Returns all location placements with GPS coordinates for map rendering.
    /// Filterable by date range and person name.
    /// </summary>
    [HttpGet("geo-timeline")]
    public async Task<ActionResult<IReadOnlyList<GeoTimelineEntryDto>>> GetGeoTimeline(
        [FromQuery] string? dateFrom = null,
        [FromQuery] string? dateTo = null,
        [FromQuery] string? personName = null,
        [FromQuery] long? locationId = null,
        [FromQuery] int limit = 2000,
        CancellationToken cancellationToken = default)
    {
        var conn = _context.Database.GetDbConnection();

        var conditions = new List<string> { "l.latitude IS NOT NULL", "l.longitude IS NOT NULL" };
        var parameters = new DynamicParameters();
        parameters.Add("Limit", limit);

        if (!string.IsNullOrWhiteSpace(dateFrom))
        {
            conditions.Add("plp.placement_date >= @DateFrom::date");
            parameters.Add("DateFrom", dateFrom);
        }
        if (!string.IsNullOrWhiteSpace(dateTo))
        {
            conditions.Add("plp.placement_date <= @DateTo::date");
            parameters.Add("DateTo", dateTo);
        }
        if (!string.IsNullOrWhiteSpace(personName))
        {
            conditions.Add("plp.person_name ILIKE @PersonName");
            parameters.Add("PersonName", $"%{personName}%");
        }
        if (locationId.HasValue)
        {
            conditions.Add("plp.location_id = @LocationId");
            parameters.Add("LocationId", locationId.Value);
        }

        var where = string.Join(" AND ", conditions);
        var sql = $"""
            SELECT
                plp.placement_id     AS PlacementId,
                plp.location_id      AS LocationId,
                l.location_name      AS LocationName,
                l.latitude           AS Latitude,
                l.longitude          AS Longitude,
                l.city               AS City,
                l.country            AS Country,
                l.location_type      AS LocationType,
                plp.person_name      AS PersonName,
                plp.person_id        AS PersonId,
                plp.placement_date   AS PlacementDate,
                plp.date_end         AS DateEnd,
                plp.activity_type    AS ActivityType,
                plp.description      AS Description,
                plp.confidence       AS Confidence
            FROM person_location_placements plp
            JOIN locations l ON l.location_id = plp.location_id
            WHERE {where}
            ORDER BY plp.placement_date DESC
            LIMIT @Limit
            """;

        var results = await conn.QueryAsync<GeoTimelineEntryDto>(sql, parameters);
        return Ok(results.ToList());
    }

    /// <summary>
    /// Returns all connections for a person: locations, events, financial transactions,
    /// related people (from relationships table), and co-presences (shared locations).
    /// </summary>
    [HttpGet("person/{personId:long}/connections")]
    public async Task<ActionResult<PersonConnectionsDto>> GetPersonConnections(
        long personId,
        [FromQuery] string? dateFrom = null,
        [FromQuery] string? dateTo = null,
        CancellationToken cancellationToken = default)
    {
        var conn = _context.Database.GetDbConnection();

        // --- Person base info ---
        var person = await conn.QueryFirstOrDefaultAsync<(long PersonId, string PersonName, string? PrimaryRole, string? EpsteinRelationship)>(
            """
            SELECT person_id AS PersonId, full_name AS PersonName,
                   primary_role AS PrimaryRole, epstein_relationship AS EpsteinRelationship
            FROM people WHERE person_id = @PersonId
            """,
            new { PersonId = personId });

        if (person.PersonId == 0) return NotFound();

        var dateParams = new DynamicParameters();
        dateParams.Add("PersonId", personId);
        var dateConds = new List<string>();
        if (!string.IsNullOrWhiteSpace(dateFrom)) { dateConds.Add("plp.placement_date >= @DateFrom::date"); dateParams.Add("DateFrom", dateFrom); }
        if (!string.IsNullOrWhiteSpace(dateTo)) { dateConds.Add("plp.placement_date <= @DateTo::date"); dateParams.Add("DateTo", dateTo); }
        var dateWhere = dateConds.Count > 0 ? "AND " + string.Join(" AND ", dateConds) : "";

        // --- Locations visited ---
        var locationsSql = $"""
            SELECT
                l.location_id     AS LocationId,
                l.location_name   AS LocationName,
                l.city            AS City,
                l.country         AS Country,
                l.latitude        AS Latitude,
                l.longitude       AS Longitude,
                COUNT(*)          AS VisitCount,
                MIN(plp.placement_date) AS FirstVisit,
                MAX(plp.placement_date) AS LastVisit,
                (SELECT activity_type FROM person_location_placements
                 WHERE person_id = @PersonId AND location_id = l.location_id
                 ORDER BY placement_date DESC NULLS LAST LIMIT 1) AS MostRecentActivityType
            FROM person_location_placements plp
            JOIN locations l ON l.location_id = plp.location_id
            WHERE plp.person_id = @PersonId {dateWhere}
            GROUP BY l.location_id, l.location_name, l.city, l.country, l.latitude, l.longitude
            ORDER BY COUNT(*) DESC
            LIMIT 100
            """;
        var locations = (await conn.QueryAsync<ConnectedLocationDto>(locationsSql, dateParams)).ToList();

        // --- Events participated in ---
        var eventsSql = $"""
            SELECT
                e.event_id           AS EventId,
                e.event_type         AS EventType,
                e.title              AS Title,
                e.event_date         AS EventDate,
                l.location_name      AS LocationName,
                e.location_id        AS LocationId,
                ep.participation_role AS ParticipationRole
            FROM event_participants ep
            JOIN events e ON e.event_id = ep.event_id
            LEFT JOIN locations l ON l.location_id = e.location_id
            WHERE ep.person_id = @PersonId
            ORDER BY e.event_date DESC NULLS LAST
            LIMIT 100
            """;
        var events = (await conn.QueryAsync<ConnectedEventDto>(eventsSql, new { PersonId = personId })).ToList();

        // --- Financial transactions ---
        var financialSql = """
            SELECT
                ft.transaction_id   AS TransactionId,
                'sent'              AS Direction,
                ft.amount           AS Amount,
                ft.currency         AS Currency,
                COALESCE(tp.full_name, torg.organization_name, ft.to_account) AS CounterpartyName,
                ft.transaction_date AS TransactionDate,
                ft.purpose          AS Purpose
            FROM financial_transactions ft
            LEFT JOIN people tp ON tp.person_id = ft.to_person_id
            LEFT JOIN organizations torg ON torg.organization_id = ft.to_organization_id
            WHERE ft.from_person_id = @PersonId

            UNION ALL

            SELECT
                ft.transaction_id   AS TransactionId,
                'received'          AS Direction,
                ft.amount           AS Amount,
                ft.currency         AS Currency,
                COALESCE(fp.full_name, forg.organization_name, ft.from_account) AS CounterpartyName,
                ft.transaction_date AS TransactionDate,
                ft.purpose          AS Purpose
            FROM financial_transactions ft
            LEFT JOIN people fp ON fp.person_id = ft.from_person_id
            LEFT JOIN organizations forg ON forg.organization_id = ft.from_organization_id
            WHERE ft.to_person_id = @PersonId

            ORDER BY TransactionDate DESC NULLS LAST
            LIMIT 100
            """;
        var financial = (await conn.QueryAsync<ConnectedFinancialDto>(financialSql, new { PersonId = personId })).ToList();

        // --- Related people from relationships table ---
        var relPeopleSql = """
            SELECT
                CASE WHEN r.person1_id = @PersonId THEN r.person2_id ELSE r.person1_id END AS PersonId,
                CASE WHEN r.person1_id = @PersonId THEN p2.full_name ELSE p1.full_name END AS PersonName,
                r.relationship_type AS RelationshipType,
                CASE WHEN r.person1_id = @PersonId THEN p2.primary_role ELSE p1.primary_role END AS PrimaryRole,
                'relationship' AS Source,
                1 AS SharedCount
            FROM relationships r
            JOIN people p1 ON p1.person_id = r.person1_id
            JOIN people p2 ON p2.person_id = r.person2_id
            WHERE r.person1_id = @PersonId OR r.person2_id = @PersonId
            ORDER BY r.relationship_type
            LIMIT 100
            """;
        var relatedFromRelationships = (await conn.QueryAsync<ConnectedPersonDto>(relPeopleSql, new { PersonId = personId })).ToList();

        // --- Co-presences: people at same locations within 30 days ---
        var coPresenceSql = $"""
            SELECT DISTINCT ON (other.person_name, subj.location_id)
                other.person_name                    AS OtherPersonName,
                other.person_id                      AS OtherPersonId,
                subj.location_id                     AS LocationId,
                l.location_name                      AS LocationName,
                subj.placement_date                  AS SubjectDate,
                other.placement_date                 AS OtherDate,
                other.activity_type                  AS ActivityType,
                ABS(other.placement_date - subj.placement_date) AS OverlapDays
            FROM person_location_placements subj
            JOIN person_location_placements other
                ON other.location_id = subj.location_id
               AND other.person_name != subj.person_name
               AND other.person_id != @PersonId
               AND ABS(other.placement_date - subj.placement_date) <= 30
            JOIN locations l ON l.location_id = subj.location_id
            WHERE subj.person_id = @PersonId {dateWhere}
            ORDER BY other.person_name, subj.location_id, ABS(other.placement_date - subj.placement_date)
            LIMIT 200
            """;
        var coPresences = (await conn.QueryAsync<CoPresenceDto>(coPresenceSql, dateParams)).ToList();

        // --- Co-located people summary for related people list ---
        var coLocatedSql = $"""
            SELECT
                other.person_name AS PersonName,
                other.person_id   AS PersonId,
                COUNT(*)          AS SharedCount,
                'co-location'     AS Source,
                NULL              AS RelationshipType,
                NULL              AS PrimaryRole
            FROM person_location_placements subj
            JOIN person_location_placements other
                ON other.location_id = subj.location_id
               AND other.person_name != subj.person_name
               AND (other.person_id IS NULL OR other.person_id != @PersonId)
               AND ABS(other.placement_date - subj.placement_date) <= 30
            WHERE subj.person_id = @PersonId {dateWhere}
            GROUP BY other.person_name, other.person_id
            ORDER BY COUNT(*) DESC
            LIMIT 50
            """;
        var coLocated = (await conn.QueryAsync<ConnectedPersonDto>(coLocatedSql, dateParams)).ToList();

        // Merge related people: relationships first, then co-located (no duplicates by name)
        var relatedNames = relatedFromRelationships.Select(r => r.PersonName.ToLowerInvariant()).ToHashSet();
        var merged = relatedFromRelationships
            .Concat(coLocated.Where(cl => !relatedNames.Contains(cl.PersonName.ToLowerInvariant())))
            .ToList();

        return Ok(new PersonConnectionsDto
        {
            PersonId = person.PersonId,
            PersonName = person.PersonName,
            PrimaryRole = person.PrimaryRole,
            EpsteinRelationship = person.EpsteinRelationship,
            Locations = locations,
            Events = events,
            FinancialTransactions = financial,
            RelatedPeople = merged,
            CoPresences = coPresences,
        });
    }

    /// <summary>
    /// Returns locations where 2 or more of the given person IDs were present within 30 days of each other.
    /// Used to show "hot spots" where multiple investigation subjects converged.
    /// </summary>
    [HttpGet("shared-presence")]
    public async Task<ActionResult<IReadOnlyList<SharedPresenceDto>>> GetSharedPresence(
        [FromQuery] string personIds = "",
        [FromQuery] string? dateFrom = null,
        [FromQuery] string? dateTo = null,
        CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(personIds)) return Ok(Array.Empty<SharedPresenceDto>());

        var ids = personIds.Split(',')
            .Select(s => long.TryParse(s.Trim(), out var v) ? (long?)v : null)
            .Where(v => v.HasValue)
            .Select(v => v!.Value)
            .Distinct()
            .ToArray();

        if (ids.Length < 2) return Ok(Array.Empty<SharedPresenceDto>());

        var conn = _context.Database.GetDbConnection();
        var parameters = new DynamicParameters();
        parameters.Add("Ids", ids);

        var dateConds = new List<string>();
        if (!string.IsNullOrWhiteSpace(dateFrom)) { dateConds.Add("plp.placement_date >= @DateFrom::date"); parameters.Add("DateFrom", dateFrom); }
        if (!string.IsNullOrWhiteSpace(dateTo)) { dateConds.Add("plp.placement_date <= @DateTo::date"); parameters.Add("DateTo", dateTo); }
        var dateWhere = dateConds.Count > 0 ? "AND " + string.Join(" AND ", dateConds) : "";

        var sql = $"""
            SELECT
                l.location_id    AS LocationId,
                l.location_name  AS LocationName,
                l.city           AS City,
                l.country        AS Country,
                l.latitude       AS Latitude,
                l.longitude      AS Longitude,
                COUNT(DISTINCT plp.person_id) AS PersonCount,
                MIN(plp.placement_date)        AS EarliestDate,
                MAX(plp.placement_date)        AS LatestDate,
                STRING_AGG(DISTINCT plp.person_name, ', ' ORDER BY plp.person_name) AS PersonNamesRaw
            FROM person_location_placements plp
            JOIN locations l ON l.location_id = plp.location_id
            WHERE plp.person_id = ANY(@Ids) {dateWhere}
            GROUP BY l.location_id, l.location_name, l.city, l.country, l.latitude, l.longitude
            HAVING COUNT(DISTINCT plp.person_id) >= 2
            ORDER BY COUNT(DISTINCT plp.person_id) DESC, COUNT(*) DESC
            LIMIT 100
            """;

        // Use a flat DTO for Dapper mapping, then reconstruct PersonNames from the aggregated string
        var rows = await conn.QueryAsync<SharedPresenceFlatDto>(sql, parameters);
        var results = rows.Select(r => new SharedPresenceDto
        {
            LocationId = r.LocationId,
            LocationName = r.LocationName,
            City = r.City,
            Country = r.Country,
            Latitude = r.Latitude,
            Longitude = r.Longitude,
            PersonCount = r.PersonCount,
            PersonNames = (r.PersonNamesRaw ?? "").Split(", ", StringSplitOptions.RemoveEmptyEntries).ToList(),
            EarliestDate = r.EarliestDate,
            LatestDate = r.LatestDate,
        }).ToList();

        return Ok(results);
    }

    /// <summary>
    /// Financial flows between a set of people — for the financial network panel.
    /// </summary>
    [HttpGet("financial-network")]
    public async Task<ActionResult<IReadOnlyList<ConnectedFinancialDto>>> GetFinancialNetwork(
        [FromQuery] string personIds = "",
        [FromQuery] string? dateFrom = null,
        [FromQuery] string? dateTo = null,
        CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(personIds)) return Ok(Array.Empty<ConnectedFinancialDto>());

        var ids = personIds.Split(',')
            .Select(s => long.TryParse(s.Trim(), out var v) ? (long?)v : null)
            .Where(v => v.HasValue)
            .Select(v => v!.Value)
            .Distinct()
            .ToArray();

        if (ids.Length == 0) return Ok(Array.Empty<ConnectedFinancialDto>());

        var conn = _context.Database.GetDbConnection();
        var parameters = new DynamicParameters();
        parameters.Add("Ids", ids);

        var dateConds = new List<string>();
        if (!string.IsNullOrWhiteSpace(dateFrom)) { dateConds.Add("ft.transaction_date >= @DateFrom"); parameters.Add("DateFrom", dateFrom); }
        if (!string.IsNullOrWhiteSpace(dateTo)) { dateConds.Add("ft.transaction_date <= @DateTo"); parameters.Add("DateTo", dateTo); }
        var dateWhere = dateConds.Count > 0 ? "AND " + string.Join(" AND ", dateConds) : "";

        var sql = $"""
            SELECT
                ft.transaction_id   AS TransactionId,
                COALESCE(fp.full_name, 'Unknown') AS Direction,
                ft.amount           AS Amount,
                ft.currency         AS Currency,
                COALESCE(tp.full_name, torg.organization_name, ft.to_account) AS CounterpartyName,
                ft.transaction_date AS TransactionDate,
                ft.purpose          AS Purpose
            FROM financial_transactions ft
            LEFT JOIN people fp ON fp.person_id = ft.from_person_id
            LEFT JOIN people tp ON tp.person_id = ft.to_person_id
            LEFT JOIN organizations torg ON torg.organization_id = ft.to_organization_id
            WHERE (ft.from_person_id = ANY(@Ids) OR ft.to_person_id = ANY(@Ids)) {dateWhere}
            ORDER BY ft.transaction_date DESC NULLS LAST
            LIMIT 200
            """;

        var results = (await conn.QueryAsync<ConnectedFinancialDto>(sql, parameters)).ToList();
        return Ok(results);
    }

    // Private flat DTO for Dapper mapping of shared presence query
    private sealed class SharedPresenceFlatDto
    {
        public long LocationId { get; init; }
        public string LocationName { get; init; } = string.Empty;
        public string? City { get; init; }
        public string? Country { get; init; }
        public double? Latitude { get; init; }
        public double? Longitude { get; init; }
        public int PersonCount { get; init; }
        public string? PersonNamesRaw { get; init; }
        public DateTime? EarliestDate { get; init; }
        public DateTime? LatestDate { get; init; }
    }
}
