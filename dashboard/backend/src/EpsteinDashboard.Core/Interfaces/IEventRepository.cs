using EpsteinDashboard.Core.Entities;
using EpsteinDashboard.Core.Models;

namespace EpsteinDashboard.Core.Interfaces;

public interface IEventRepository : IRepository<Event>
{
    Task<Event?> GetWithParticipantsAsync(long id, CancellationToken cancellationToken = default);
    Task<PagedResult<Event>> GetFilteredAsync(int page, int pageSize, string? eventType = null, string? dateFrom = null, string? dateTo = null, string? sortBy = null, string? sortDirection = null, CancellationToken cancellationToken = default);
}
