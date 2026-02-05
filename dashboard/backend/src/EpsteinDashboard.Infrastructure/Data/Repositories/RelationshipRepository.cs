using EpsteinDashboard.Core.Entities;
using EpsteinDashboard.Core.Interfaces;
using Microsoft.EntityFrameworkCore;

namespace EpsteinDashboard.Infrastructure.Data.Repositories;

public class RelationshipRepository : BaseRepository<Relationship>, IRelationshipRepository
{
    public RelationshipRepository(EpsteinDbContext context) : base(context)
    {
    }

    public override async Task<Relationship?> GetByIdAsync(long id, CancellationToken cancellationToken = default)
    {
        return await DbSet.AsNoTracking()
            .Include(r => r.Person1)
            .Include(r => r.Person2)
            .Include(r => r.SourceDocument)
            .FirstOrDefaultAsync(r => r.RelationshipId == id, cancellationToken);
    }

    public async Task<IReadOnlyList<Relationship>> GetByPersonIdAsync(long personId, CancellationToken cancellationToken = default)
    {
        return await DbSet.AsNoTracking()
            .Include(r => r.Person1)
            .Include(r => r.Person2)
            .Where(r => r.Person1Id == personId || r.Person2Id == personId)
            .ToListAsync(cancellationToken);
    }
}
