using EpsteinDashboard.Core.Entities;

namespace EpsteinDashboard.Core.Interfaces;

public interface ILocationRepository : IRepository<Location>
{
    Task<Location?> GetWithDetailsAsync(long id, CancellationToken cancellationToken = default);
}
