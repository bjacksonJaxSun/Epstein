using EpsteinDashboard.Core.Entities;
using EpsteinDashboard.Core.Models;

namespace EpsteinDashboard.Core.Interfaces;

public interface ICommunicationRepository : IRepository<Communication>
{
    Task<Communication?> GetWithRecipientsAsync(long id, CancellationToken cancellationToken = default);
    Task<PagedResult<Communication>> GetFilteredAsync(int page, int pageSize, string? communicationType = null, string? sortBy = null, string? sortDirection = null, CancellationToken cancellationToken = default);
}
