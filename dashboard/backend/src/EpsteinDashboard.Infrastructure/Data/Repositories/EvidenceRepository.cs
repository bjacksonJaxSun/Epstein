using EpsteinDashboard.Core.Entities;
using EpsteinDashboard.Core.Interfaces;
using Microsoft.EntityFrameworkCore;

namespace EpsteinDashboard.Infrastructure.Data.Repositories;

public class EvidenceRepository : BaseRepository<EvidenceItem>, IEvidenceRepository
{
    public EvidenceRepository(EpsteinDbContext context) : base(context)
    {
    }

    public async Task<EvidenceItem?> GetWithDetailsAsync(long id, CancellationToken cancellationToken = default)
    {
        return await DbSet.AsNoTracking()
            .Include(e => e.SeizedFromLocation)
            .Include(e => e.SeizedFromPerson)
            .Include(e => e.SourceDocument)
            .Include(e => e.MediaFiles)
            .FirstOrDefaultAsync(e => e.EvidenceId == id, cancellationToken);
    }
}
