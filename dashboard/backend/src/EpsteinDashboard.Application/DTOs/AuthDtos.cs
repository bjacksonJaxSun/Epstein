namespace EpsteinDashboard.Application.DTOs;

public record LoginRequest(string Username, string Password);

public record LoginResponse(
    string AccessToken,
    string RefreshToken,
    DateTime AccessTokenExpires,
    DateTime RefreshTokenExpires,
    UserDto User
);

public record RefreshTokenRequest(string RefreshToken);

public record UserDto(
    long UserId,
    string Username,
    string Email,
    IReadOnlyList<string> Roles,
    int MaxTierLevel,
    bool IsActive,
    DateTime? LastLoginAt
);

public record ErrorResponse(string Error, string? Details = null);
