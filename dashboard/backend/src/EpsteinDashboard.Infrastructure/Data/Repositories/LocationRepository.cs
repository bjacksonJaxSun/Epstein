using Dapper;
using EpsteinDashboard.Core.Entities;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Microsoft.EntityFrameworkCore;

namespace EpsteinDashboard.Infrastructure.Data.Repositories;

public class LocationRepository : BaseRepository<Location>, ILocationRepository
{
    public LocationRepository(EpsteinDbContext context) : base(context)
    {
    }

    public async Task<Location?> GetWithDetailsAsync(long id, CancellationToken cancellationToken = default)
    {
        return await DbSet.AsNoTracking()
            .Include(l => l.OwnerPerson)
            .Include(l => l.OwnerOrganization)
            .Include(l => l.Events)
            .Include(l => l.FirstMentionedInDocument)
            .FirstOrDefaultAsync(l => l.LocationId == id, cancellationToken);
    }

    public async Task<PagedResult<(Location Location, string? OwnerName, int EventCount, int MediaCount, int EvidenceCount, int PlacementCount, int TotalActivity)>>
        GetPagedWithCountsAsync(
            int page,
            int pageSize,
            string? search = null,
            string? locationType = null,
            string? country = null,
            string? sortBy = null,
            string? sortDirection = null,
            CancellationToken cancellationToken = default)
    {
        var connection = Context.Database.GetDbConnection();

        var whereConditions = new List<string> { "1=1" };
        var parameters = new DynamicParameters();

        if (!string.IsNullOrWhiteSpace(search))
        {
            whereConditions.Add("(l.location_name LIKE @Search OR l.city LIKE @Search OR l.country LIKE @Search OR l.description LIKE @Search)");
            parameters.Add("Search", $"%{search}%");
        }

        if (!string.IsNullOrWhiteSpace(locationType))
        {
            whereConditions.Add("l.location_type = @LocationType");
            parameters.Add("LocationType", locationType);
        }

        if (!string.IsNullOrWhiteSpace(country))
        {
            whereConditions.Add("l.country = @Country");
            parameters.Add("Country", country);
        }

        var whereClause = string.Join(" AND ", whereConditions);

        // Validate and map sort column
        var validSortColumns = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["locationName"] = "l.location_name",
            ["locationType"] = "l.location_type",
            ["city"] = "l.city",
            ["country"] = "l.country",
            ["eventCount"] = "EventCount",
            ["mediaCount"] = "MediaCount",
            ["evidenceCount"] = "EvidenceCount",
            ["placementCount"] = "PlacementCount",
            ["totalActivity"] = "TotalActivity"
        };

        var orderColumn = "TotalActivity";
        if (!string.IsNullOrWhiteSpace(sortBy) && validSortColumns.TryGetValue(sortBy, out var mappedColumn))
        {
            orderColumn = mappedColumn;
        }

        var orderDirection = sortDirection?.ToLowerInvariant() == "asc" ? "ASC" : "DESC";

        // Count query
        var countSql = $@"
            SELECT COUNT(DISTINCT l.location_id)
            FROM locations l
            WHERE {whereClause}";

        var totalCount = await connection.ExecuteScalarAsync<int>(
            new CommandDefinition(countSql, parameters, cancellationToken: cancellationToken));

        // Main query with counts using aggregate subqueries (pre-computed for efficiency)
        var sql = $@"
            SELECT
                l.location_id AS LocationId,
                l.location_name AS LocationName,
                l.location_type AS LocationType,
                l.street_address AS StreetAddress,
                l.city AS City,
                l.state_province AS StateProvince,
                l.country AS Country,
                l.postal_code AS PostalCode,
                l.latitude AS Latitude,
                l.longitude AS Longitude,
                l.description AS Description,
                COALESCE(p.full_name, o.organization_name) AS OwnerName,
                l.created_at AS CreatedAt,
                l.updated_at AS UpdatedAt,
                COALESCE(ec.cnt, 0) AS EventCount,
                COALESCE(mc.cnt, 0) AS MediaCount,
                COALESCE(evc.cnt, 0) AS EvidenceCount,
                COALESCE(plc.cnt, 0) AS PlacementCount,
                COALESCE(ec.cnt, 0) + COALESCE(mc.cnt, 0) + COALESCE(evc.cnt, 0) + COALESCE(plc.cnt, 0) AS TotalActivity
            FROM locations l
            LEFT JOIN people p ON l.owner_person_id = p.person_id
            LEFT JOIN organizations o ON l.owner_organization_id = o.organization_id
            LEFT JOIN (SELECT location_id, COUNT(*) as cnt FROM events GROUP BY location_id) ec ON ec.location_id = l.location_id
            LEFT JOIN (SELECT location_id, COUNT(*) as cnt FROM media_files GROUP BY location_id) mc ON mc.location_id = l.location_id
            LEFT JOIN (SELECT seized_from_location_id, COUNT(*) as cnt FROM evidence_items GROUP BY seized_from_location_id) evc ON evc.seized_from_location_id = l.location_id
            LEFT JOIN (SELECT location_id, COUNT(*) as cnt FROM person_location_placements GROUP BY location_id) plc ON plc.location_id = l.location_id
            WHERE {whereClause}
            ORDER BY {orderColumn} {orderDirection}
            LIMIT @PageSize OFFSET @Offset";

        parameters.Add("PageSize", pageSize);
        parameters.Add("Offset", page * pageSize);

        var results = await connection.QueryAsync<LocationWithCounts>(
            new CommandDefinition(sql, parameters, cancellationToken: cancellationToken));

        var items = results.Select(r => (
            Location: new Location
            {
                LocationId = r.LocationId,
                LocationName = r.LocationName,
                LocationType = r.LocationType,
                StreetAddress = r.StreetAddress,
                City = r.City,
                StateProvince = r.StateProvince,
                Country = r.Country,
                PostalCode = r.PostalCode,
                Latitude = r.Latitude,
                Longitude = r.Longitude,
                Description = r.Description,
                CreatedAt = r.CreatedAt,
                UpdatedAt = r.UpdatedAt
            },
            OwnerName: r.OwnerName,
            EventCount: r.EventCount,
            MediaCount: r.MediaCount,
            EvidenceCount: r.EvidenceCount,
            PlacementCount: r.PlacementCount,
            TotalActivity: r.TotalActivity
        )).ToList();

        return new PagedResult<(Location Location, string? OwnerName, int EventCount, int MediaCount, int EvidenceCount, int PlacementCount, int TotalActivity)>
        {
            Items = items,
            TotalCount = totalCount,
            Page = page,
            PageSize = pageSize
        };
    }

    public async Task<IReadOnlyList<Document>> GetDocumentsForLocationAsync(long locationId, CancellationToken cancellationToken = default)
    {
        var connection = Context.Database.GetDbConnection();

        // Get documents where this location is first mentioned, plus documents linked through events
        var sql = @"
            SELECT DISTINCT
                d.document_id AS DocumentId,
                d.efta_number AS EftaNumber,
                d.file_path AS FilePath,
                d.document_type AS DocumentType,
                d.document_date AS DocumentDate,
                d.document_title AS DocumentTitle,
                d.author AS Author,
                d.recipient AS Recipient,
                d.subject AS Subject,
                d.page_count AS PageCount,
                d.file_size_bytes AS FileSizeBytes,
                d.classification_level AS ClassificationLevel,
                d.is_redacted AS IsRedacted,
                d.source_agency AS SourceAgency,
                d.created_at AS CreatedAt,
                d.updated_at AS UpdatedAt
            FROM documents d
            WHERE d.document_id IN (
                -- Document where location was first mentioned
                SELECT first_mentioned_in_doc_id FROM locations WHERE location_id = @LocationId AND first_mentioned_in_doc_id IS NOT NULL
                UNION
                -- Documents linked through events at this location
                SELECT e.source_document_id FROM events e WHERE e.location_id = @LocationId AND e.source_document_id IS NOT NULL
                UNION
                -- Documents linked through person-location placements
                SELECT UNNEST(plp.source_document_ids) FROM person_location_placements plp WHERE plp.location_id = @LocationId AND plp.source_document_ids IS NOT NULL
            )
            ORDER BY d.document_date DESC, d.document_id DESC
            LIMIT 50";

        var results = await connection.QueryAsync<Document>(
            new CommandDefinition(sql, new { LocationId = locationId }, cancellationToken: cancellationToken));

        return results.ToList();
    }

    public async Task<IReadOnlyList<LocationPlacementRecord>> GetPlacementsForLocationAsync(
        long locationId,
        int limit = 100,
        CancellationToken cancellationToken = default)
    {
        var connection = Context.Database.GetDbConnection();

        // Query placements for a location, ordered by date and confidence
        var sql = @"
            SELECT
                plp.placement_id AS PlacementId,
                plp.person_id AS PersonId,
                plp.person_name AS PersonName,
                plp.placement_date AS PlacementDate,
                plp.date_end AS DateEnd,
                plp.date_precision AS DatePrecision,
                plp.activity_type AS ActivityType,
                plp.description AS Description,
                plp.source_document_ids AS SourceDocumentIds,
                plp.source_efta_numbers AS SourceEftaNumbers,
                plp.evidence_excerpts AS EvidenceExcerpts,
                plp.confidence AS Confidence,
                plp.extraction_method AS ExtractionMethod
            FROM person_location_placements plp
            WHERE plp.location_id = @LocationId
            ORDER BY plp.placement_date DESC NULLS LAST, plp.confidence DESC NULLS LAST
            LIMIT @Limit";

        var rawResults = await connection.QueryAsync<PlacementRawRecord>(
            new CommandDefinition(sql, new { LocationId = locationId, Limit = limit }, cancellationToken: cancellationToken));

        // Map to LocationPlacementRecord, handling nullable arrays
        var results = rawResults.Select(r => new LocationPlacementRecord
        {
            PlacementId = r.PlacementId,
            PersonId = r.PersonId,
            PersonName = r.PersonName ?? string.Empty,
            PlacementDate = r.PlacementDate,
            DateEnd = r.DateEnd,
            DatePrecision = r.DatePrecision,
            ActivityType = r.ActivityType,
            Description = r.Description,
            SourceDocumentIds = r.SourceDocumentIds?.Select(id => (long)id).ToArray(),
            SourceEftaNumbers = r.SourceEftaNumbers,
            EvidenceExcerpts = r.EvidenceExcerpts,
            Confidence = r.Confidence,
            ExtractionMethod = r.ExtractionMethod
        }).ToList();

        return results;
    }

    // Private class for raw Dapper mapping (handles PostgreSQL arrays)
    private class PlacementRawRecord
    {
        public long PlacementId { get; set; }
        public long? PersonId { get; set; }
        public string? PersonName { get; set; }
        public DateTime? PlacementDate { get; set; }
        public DateTime? DateEnd { get; set; }
        public string? DatePrecision { get; set; }
        public string? ActivityType { get; set; }
        public string? Description { get; set; }
        public int[]? SourceDocumentIds { get; set; }
        public string[]? SourceEftaNumbers { get; set; }
        public string[]? EvidenceExcerpts { get; set; }
        public decimal? Confidence { get; set; }
        public string? ExtractionMethod { get; set; }
    }

    private class LocationWithCounts
    {
        public long LocationId { get; set; }
        public string LocationName { get; set; } = string.Empty;
        public string? LocationType { get; set; }
        public string? StreetAddress { get; set; }
        public string? City { get; set; }
        public string? StateProvince { get; set; }
        public string? Country { get; set; }
        public string? PostalCode { get; set; }
        public double? Latitude { get; set; }
        public double? Longitude { get; set; }
        public string? OwnerName { get; set; }
        public string? Description { get; set; }
        public DateTime? CreatedAt { get; set; }
        public DateTime? UpdatedAt { get; set; }
        public int EventCount { get; set; }
        public int MediaCount { get; set; }
        public int EvidenceCount { get; set; }
        public int PlacementCount { get; set; }
        public int TotalActivity { get; set; }
    }
}
