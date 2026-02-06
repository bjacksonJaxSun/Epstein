using EpsteinDashboard.Core.Entities;
using EpsteinDashboard.Core.Models;

namespace EpsteinDashboard.Core.Interfaces;

public interface ILocationRepository : IRepository<Location>
{
    Task<Location?> GetWithDetailsAsync(long id, CancellationToken cancellationToken = default);

    Task<PagedResult<(Location Location, string? OwnerName, int EventCount, int MediaCount, int EvidenceCount, int TotalActivity)>>
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
}
