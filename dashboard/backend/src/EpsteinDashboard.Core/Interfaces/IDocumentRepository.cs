using EpsteinDashboard.Core.Entities;
using EpsteinDashboard.Core.Models;

namespace EpsteinDashboard.Core.Interfaces;

public interface IDocumentRepository : IRepository<Document>
{
    Task<Document?> GetByEftaNumberAsync(string eftaNumber, CancellationToken cancellationToken = default);
    Task<PagedResult<Document>> GetFilteredAsync(int page, int pageSize, string? documentType = null, string? dateFrom = null, string? dateTo = null, string? sortBy = null, string? sortDirection = null, CancellationToken cancellationToken = default);
    Task<Document?> GetWithEntitiesAsync(long id, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<string>> GetDocumentTypesAsync(CancellationToken cancellationToken = default);
}
