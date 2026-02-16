using EpsteinDashboard.Application.DTOs;
using EpsteinDashboard.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace EpsteinDashboard.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class AuthController : ControllerBase
{
    private readonly IAuthService _authService;

    public AuthController(IAuthService authService)
    {
        _authService = authService;
    }

    [HttpPost("login")]
    [AllowAnonymous]
    public async Task<ActionResult<LoginResponse>> Login(
        [FromBody] LoginRequest request,
        CancellationToken cancellationToken)
    {
        var result = await _authService.LoginAsync(request.Username, request.Password, cancellationToken);

        if (!result.Success)
        {
            return Unauthorized(new ErrorResponse(result.Error ?? "Authentication failed"));
        }

        return Ok(new LoginResponse(
            result.AccessToken!,
            result.RefreshToken!,
            result.AccessTokenExpires!.Value,
            result.RefreshTokenExpires!.Value,
            new UserDto(
                result.User!.UserId,
                result.User.Username,
                result.User.Email,
                result.User.Roles,
                result.User.MaxTierLevel,
                true,
                DateTime.UtcNow
            )
        ));
    }

    [HttpPost("refresh")]
    [AllowAnonymous]
    public async Task<ActionResult<LoginResponse>> Refresh(
        [FromBody] RefreshTokenRequest request,
        CancellationToken cancellationToken)
    {
        var result = await _authService.RefreshTokenAsync(request.RefreshToken, cancellationToken);

        if (!result.Success)
        {
            return Unauthorized(new ErrorResponse(result.Error ?? "Token refresh failed"));
        }

        return Ok(new LoginResponse(
            result.AccessToken!,
            result.RefreshToken!,
            result.AccessTokenExpires!.Value,
            result.RefreshTokenExpires!.Value,
            new UserDto(
                result.User!.UserId,
                result.User.Username,
                result.User.Email,
                result.User.Roles,
                result.User.MaxTierLevel,
                true,
                null
            )
        ));
    }

    [HttpPost("logout")]
    [Authorize]
    public async Task<ActionResult> Logout(
        [FromBody] RefreshTokenRequest request,
        CancellationToken cancellationToken)
    {
        await _authService.RevokeTokenAsync(request.RefreshToken, cancellationToken);
        return Ok(new { message = "Logged out successfully" });
    }

    [HttpGet("me")]
    [Authorize]
    public ActionResult<UserDto> GetCurrentUser()
    {
        var userId = long.Parse(User.FindFirst(System.Security.Claims.ClaimTypes.NameIdentifier)?.Value ?? "0");
        var username = User.Identity?.Name ?? "";
        var email = User.FindFirst(System.Security.Claims.ClaimTypes.Email)?.Value ?? "";
        var roles = User.FindAll(System.Security.Claims.ClaimTypes.Role).Select(c => c.Value).ToList();
        var tier = int.Parse(User.FindFirst("tier")?.Value ?? "0");

        return Ok(new UserDto(userId, username, email, roles, tier, true, null));
    }
}
