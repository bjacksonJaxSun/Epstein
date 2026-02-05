using EpsteinDashboard.Core.Models;

namespace EpsteinDashboard.Core.Interfaces;

public interface IGraphQueryService
{
    Task<NetworkGraph> GetNetworkGraphAsync(long personId, int depth = 2, CancellationToken cancellationToken = default);
    Task<ConnectionPath> FindConnectionPathAsync(long person1Id, long person2Id, int maxDepth = 6, CancellationToken cancellationToken = default);
}
