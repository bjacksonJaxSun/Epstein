using EpsteinDashboard.Core.Entities;

namespace EpsteinDashboard.Core.Interfaces;

public interface IOrganizationRepository : IRepository<Organization>
{
    Task<Organization?> GetWithChildrenAsync(long id, CancellationToken cancellationToken = default);
}
