using EpsteinDashboard.Core.Entities;

namespace EpsteinDashboard.Core.Interfaces;

public interface IRefreshTokenRepository
{
    Task<RefreshToken?> GetByTokenHashAsync(string tokenHash, CancellationToken cancellationToken = default);
    Task<RefreshToken> CreateAsync(RefreshToken token, CancellationToken cancellationToken = default);
    Task RevokeAsync(long tokenId, long? replacedByTokenId = null, CancellationToken cancellationToken = default);
    Task RevokeAllForUserAsync(long userId, CancellationToken cancellationToken = default);
}
