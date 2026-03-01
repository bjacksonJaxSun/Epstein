using EpsteinDashboard.Core.Entities;
using EpsteinDashboard.Core.Models;

namespace EpsteinDashboard.Core.Interfaces;

public interface ILocationRepository : IRepository<Location>
{
    Task<Location?> GetWithDetailsAsync(long id, CancellationToken cancellationToken = default);

    Task<PagedResult<(Location Location, string? OwnerName, int EventCount, int MediaCount, int EvidenceCount, int PlacementCount, int TotalActivity)>>
        GetPagedWithCountsAsync(
            int page,
            int pageSize,
            string? search = null,
            string? locationType = null,
            string? country = null,
            string? sortBy = null,
            string? sortDirection = null,
            CancellationToken cancellationToken = default);

    Task<IReadOnlyList<Document>> GetDocumentsForLocationAsync(long locationId, CancellationToken cancellationToken = default);

    Task<IReadOnlyList<LocationPlacementRecord>> GetPlacementsForLocationAsync(
        long locationId,
        int limit = 100,
        CancellationToken cancellationToken = default);
}

/// <summary>
/// Record type for raw placement data from the database.
/// </summary>
public record LocationPlacementRecord
{
    public long PlacementId { get; init; }
    public long? PersonId { get; init; }
    public string PersonName { get; init; } = string.Empty;
    public DateTime? PlacementDate { get; init; }
    public DateTime? DateEnd { get; init; }
    public string? DatePrecision { get; init; }
    public string? ActivityType { get; init; }
    public string? Description { get; init; }
    public long[]? SourceDocumentIds { get; init; }
    public string[]? SourceEftaNumbers { get; init; }
    public string[]? EvidenceExcerpts { get; init; }
    public decimal? Confidence { get; init; }
    public string? ExtractionMethod { get; init; }
}
