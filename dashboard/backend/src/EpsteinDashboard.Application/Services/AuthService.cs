using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using EpsteinDashboard.Core.Entities;
using EpsteinDashboard.Core.Interfaces;
using Microsoft.Extensions.Configuration;
using Microsoft.IdentityModel.Tokens;

namespace EpsteinDashboard.Application.Services;

public class AuthService : IAuthService
{
    private readonly IUserRepository _userRepository;
    private readonly IRefreshTokenRepository _refreshTokenRepository;
    private readonly IConfiguration _configuration;

    public AuthService(
        IUserRepository userRepository,
        IRefreshTokenRepository refreshTokenRepository,
        IConfiguration configuration)
    {
        _userRepository = userRepository;
        _refreshTokenRepository = refreshTokenRepository;
        _configuration = configuration;
    }

    public async Task<AuthResult> LoginAsync(string username, string password, CancellationToken cancellationToken = default)
    {
        var user = await _userRepository.GetByUsernameWithRolesAsync(username, cancellationToken);

        if (user == null || !VerifyPassword(password, user.PasswordHash))
        {
            return new AuthResult(false, Error: "Invalid username or password");
        }

        if (!user.IsActive)
        {
            return new AuthResult(false, Error: "Account is deactivated");
        }

        await _userRepository.UpdateLastLoginAsync(user.UserId, cancellationToken);

        return await GenerateTokensAsync(user, cancellationToken);
    }

    public async Task<AuthResult> RefreshTokenAsync(string refreshToken, CancellationToken cancellationToken = default)
    {
        var tokenHash = HashToken(refreshToken);
        var storedToken = await _refreshTokenRepository.GetByTokenHashAsync(tokenHash, cancellationToken);

        if (storedToken == null)
        {
            return new AuthResult(false, Error: "Invalid refresh token");
        }

        if (!storedToken.IsActive)
        {
            // Token reuse detected - revoke all tokens for this user
            if (storedToken.IsRevoked)
            {
                await _refreshTokenRepository.RevokeAllForUserAsync(storedToken.UserId, cancellationToken);
            }
            return new AuthResult(false, Error: "Refresh token is no longer valid");
        }

        var user = storedToken.User;
        if (!user.IsActive)
        {
            return new AuthResult(false, Error: "Account is deactivated");
        }

        // Generate new tokens (rotation)
        var result = await GenerateTokensAsync(user, cancellationToken);

        // Revoke the old token, linking to the new one
        var newTokenHash = HashToken(result.RefreshToken!);
        var newStoredToken = await _refreshTokenRepository.GetByTokenHashAsync(newTokenHash, cancellationToken);
        await _refreshTokenRepository.RevokeAsync(storedToken.TokenId, newStoredToken?.TokenId, cancellationToken);

        return result;
    }

    public async Task RevokeTokenAsync(string refreshToken, CancellationToken cancellationToken = default)
    {
        var tokenHash = HashToken(refreshToken);
        var storedToken = await _refreshTokenRepository.GetByTokenHashAsync(tokenHash, cancellationToken);

        if (storedToken != null && storedToken.IsActive)
        {
            await _refreshTokenRepository.RevokeAsync(storedToken.TokenId, cancellationToken: cancellationToken);
        }
    }

    public string HashPassword(string password)
    {
        return BCrypt.Net.BCrypt.HashPassword(password, BCrypt.Net.BCrypt.GenerateSalt(12));
    }

    public bool VerifyPassword(string password, string hash)
    {
        return BCrypt.Net.BCrypt.Verify(password, hash);
    }

    private async Task<AuthResult> GenerateTokensAsync(User user, CancellationToken cancellationToken)
    {
        var roles = user.UserRoles.Select(ur => ur.Role.Name).ToList();
        var maxTierLevel = user.UserRoles.Any()
            ? user.UserRoles.Max(ur => ur.Role.TierLevel)
            : 0;

        var accessToken = GenerateAccessToken(user, roles, maxTierLevel);
        var refreshToken = GenerateRefreshToken();

        var accessExpires = DateTime.UtcNow.AddMinutes(
            _configuration.GetValue<int>("Jwt:AccessTokenExpirationMinutes", 15));
        var refreshExpires = DateTime.UtcNow.AddDays(
            _configuration.GetValue<int>("Jwt:RefreshTokenExpirationDays", 7));

        // Store refresh token
        await _refreshTokenRepository.CreateAsync(new RefreshToken
        {
            UserId = user.UserId,
            TokenHash = HashToken(refreshToken),
            ExpiresAt = refreshExpires
        }, cancellationToken);

        return new AuthResult(
            true,
            accessToken,
            refreshToken,
            accessExpires,
            refreshExpires,
            new UserInfo(user.UserId, user.Username, user.Email, roles, maxTierLevel)
        );
    }

    private string GenerateAccessToken(User user, IEnumerable<string> roles, int maxTierLevel)
    {
        var key = new SymmetricSecurityKey(
            Encoding.UTF8.GetBytes(_configuration["Jwt:Secret"]
                ?? throw new InvalidOperationException("JWT secret not configured")));

        var claims = new List<Claim>
        {
            new(JwtRegisteredClaimNames.Sub, user.UserId.ToString()),
            new(JwtRegisteredClaimNames.UniqueName, user.Username),
            new(JwtRegisteredClaimNames.Email, user.Email),
            new("tier", maxTierLevel.ToString()),
            new(JwtRegisteredClaimNames.Jti, Guid.NewGuid().ToString())
        };

        claims.AddRange(roles.Select(role => new Claim(ClaimTypes.Role, role)));

        var token = new JwtSecurityToken(
            issuer: _configuration["Jwt:Issuer"],
            audience: _configuration["Jwt:Audience"],
            claims: claims,
            expires: DateTime.UtcNow.AddMinutes(
                _configuration.GetValue<int>("Jwt:AccessTokenExpirationMinutes", 15)),
            signingCredentials: new SigningCredentials(key, SecurityAlgorithms.HmacSha256)
        );

        return new JwtSecurityTokenHandler().WriteToken(token);
    }

    private static string GenerateRefreshToken()
    {
        var randomBytes = new byte[64];
        using var rng = RandomNumberGenerator.Create();
        rng.GetBytes(randomBytes);
        return Convert.ToBase64String(randomBytes);
    }

    private static string HashToken(string token)
    {
        using var sha256 = SHA256.Create();
        var bytes = sha256.ComputeHash(Encoding.UTF8.GetBytes(token));
        return Convert.ToBase64String(bytes);
    }
}
