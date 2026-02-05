using EpsteinDashboard.Core.Entities;

namespace EpsteinDashboard.Core.Interfaces;

public interface IEvidenceRepository : IRepository<EvidenceItem>
{
    Task<EvidenceItem?> GetWithDetailsAsync(long id, CancellationToken cancellationToken = default);
}
