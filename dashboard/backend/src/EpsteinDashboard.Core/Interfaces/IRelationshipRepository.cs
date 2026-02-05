using EpsteinDashboard.Core.Entities;

namespace EpsteinDashboard.Core.Interfaces;

public interface IRelationshipRepository : IRepository<Relationship>
{
    Task<IReadOnlyList<Relationship>> GetByPersonIdAsync(long personId, CancellationToken cancellationToken = default);
}
