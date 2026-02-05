using EpsteinDashboard.Core.Entities;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Microsoft.EntityFrameworkCore;

namespace EpsteinDashboard.Infrastructure.Data.Repositories;

public class CommunicationRepository : BaseRepository<Communication>, ICommunicationRepository
{
    public CommunicationRepository(EpsteinDbContext context) : base(context)
    {
    }

    public async Task<Communication?> GetWithRecipientsAsync(long id, CancellationToken cancellationToken = default)
    {
        return await DbSet.AsNoTracking()
            .Include(c => c.SenderPerson)
            .Include(c => c.SenderOrganization)
            .Include(c => c.Recipients).ThenInclude(r => r.Person)
            .Include(c => c.Recipients).ThenInclude(r => r.Organization)
            .Include(c => c.SourceDocument)
            .FirstOrDefaultAsync(c => c.CommunicationId == id, cancellationToken);
    }

    public async Task<PagedResult<Communication>> GetFilteredAsync(
        int page, int pageSize, string? communicationType = null,
        string? sortBy = null, string? sortDirection = null,
        CancellationToken cancellationToken = default)
    {
        var query = DbSet.AsNoTracking()
            .Include(c => c.SenderPerson)
            .Include(c => c.SenderOrganization)
            .AsQueryable();

        if (!string.IsNullOrEmpty(communicationType))
            query = query.Where(c => c.CommunicationType == communicationType);

        var totalCount = await query.CountAsync(cancellationToken);

        if (!string.IsNullOrEmpty(sortBy))
            query = ApplySort(query, sortBy, sortDirection);

        var items = await query
            .Skip(page * pageSize)
            .Take(pageSize)
            .ToListAsync(cancellationToken);

        return new PagedResult<Communication>
        {
            Items = items,
            TotalCount = totalCount,
            Page = page,
            PageSize = pageSize
        };
    }
}
