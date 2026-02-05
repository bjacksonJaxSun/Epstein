using EpsteinDashboard.Core.Entities;
using EpsteinDashboard.Core.Interfaces;
using Microsoft.EntityFrameworkCore;

namespace EpsteinDashboard.Infrastructure.Data.Repositories;

public class LocationRepository : BaseRepository<Location>, ILocationRepository
{
    public LocationRepository(EpsteinDbContext context) : base(context)
    {
    }

    public async Task<Location?> GetWithDetailsAsync(long id, CancellationToken cancellationToken = default)
    {
        return await DbSet.AsNoTracking()
            .Include(l => l.OwnerPerson)
            .Include(l => l.OwnerOrganization)
            .Include(l => l.Events)
            .Include(l => l.FirstMentionedInDocument)
            .FirstOrDefaultAsync(l => l.LocationId == id, cancellationToken);
    }
}
