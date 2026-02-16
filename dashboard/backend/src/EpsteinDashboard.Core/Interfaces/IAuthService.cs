namespace EpsteinDashboard.Core.Interfaces;

public interface IAuthService
{
    Task<AuthResult> LoginAsync(string username, string password, CancellationToken cancellationToken = default);
    Task<AuthResult> RefreshTokenAsync(string refreshToken, CancellationToken cancellationToken = default);
    Task RevokeTokenAsync(string refreshToken, CancellationToken cancellationToken = default);
    string HashPassword(string password);
    bool VerifyPassword(string password, string hash);
}

public record AuthResult(
    bool Success,
    string? AccessToken = null,
    string? RefreshToken = null,
    DateTime? AccessTokenExpires = null,
    DateTime? RefreshTokenExpires = null,
    UserInfo? User = null,
    string? Error = null
);

public record UserInfo(
    long UserId,
    string Username,
    string Email,
    IReadOnlyList<string> Roles,
    int MaxTierLevel
);
