using EpsteinDashboard.Core.Entities;
using EpsteinDashboard.Core.Interfaces;
using Microsoft.EntityFrameworkCore;

namespace EpsteinDashboard.Infrastructure.Data.Repositories;

public class OrganizationRepository : BaseRepository<Organization>, IOrganizationRepository
{
    public OrganizationRepository(EpsteinDbContext context) : base(context)
    {
    }

    public async Task<Organization?> GetWithChildrenAsync(long id, CancellationToken cancellationToken = default)
    {
        return await DbSet.AsNoTracking()
            .Include(o => o.ChildOrganizations)
            .Include(o => o.ParentOrganization)
            .Include(o => o.FirstMentionedInDocument)
            .FirstOrDefaultAsync(o => o.OrganizationId == id, cancellationToken);
    }
}
