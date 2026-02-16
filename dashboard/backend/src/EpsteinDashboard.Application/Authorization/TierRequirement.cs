using Microsoft.AspNetCore.Authorization;

namespace EpsteinDashboard.Application.Authorization;

public class TierRequirement : IAuthorizationRequirement
{
    public int MinimumTier { get; }

    public TierRequirement(int minimumTier)
    {
        MinimumTier = minimumTier;
    }
}

public class TierRequirementHandler : AuthorizationHandler<TierRequirement>
{
    protected override Task HandleRequirementAsync(
        AuthorizationHandlerContext context,
        TierRequirement requirement)
    {
        var tierClaim = context.User.FindFirst("tier");

        if (tierClaim != null && int.TryParse(tierClaim.Value, out var tier))
        {
            if (tier >= requirement.MinimumTier)
            {
                context.Succeed(requirement);
            }
        }

        return Task.CompletedTask;
    }
}
