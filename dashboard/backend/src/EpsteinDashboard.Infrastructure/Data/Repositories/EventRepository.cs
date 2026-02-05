using EpsteinDashboard.Core.Entities;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Microsoft.EntityFrameworkCore;

namespace EpsteinDashboard.Infrastructure.Data.Repositories;

public class EventRepository : BaseRepository<Event>, IEventRepository
{
    public EventRepository(EpsteinDbContext context) : base(context)
    {
    }

    public async Task<Event?> GetWithParticipantsAsync(long id, CancellationToken cancellationToken = default)
    {
        return await DbSet.AsNoTracking()
            .Include(e => e.Participants).ThenInclude(p => p.Person)
            .Include(e => e.Participants).ThenInclude(p => p.Organization)
            .Include(e => e.Location)
            .Include(e => e.SourceDocument)
            .FirstOrDefaultAsync(e => e.EventId == id, cancellationToken);
    }

    public async Task<PagedResult<Event>> GetFilteredAsync(
        int page, int pageSize, string? eventType = null,
        string? dateFrom = null, string? dateTo = null,
        string? sortBy = null, string? sortDirection = null,
        CancellationToken cancellationToken = default)
    {
        var query = DbSet.AsNoTracking()
            .Include(e => e.Location);

        if (!string.IsNullOrEmpty(eventType))
            query = query.Where(e => e.EventType == eventType).Include(e => e.Location);

        IQueryable<Event> filteredQuery = query;

        if (!string.IsNullOrEmpty(dateFrom))
            filteredQuery = filteredQuery.Where(e => string.Compare(e.EventDate, dateFrom) >= 0);

        if (!string.IsNullOrEmpty(dateTo))
            filteredQuery = filteredQuery.Where(e => string.Compare(e.EventDate, dateTo) <= 0);

        var totalCount = await filteredQuery.CountAsync(cancellationToken);

        if (!string.IsNullOrEmpty(sortBy))
            filteredQuery = ApplySort(filteredQuery, sortBy, sortDirection);

        var items = await filteredQuery
            .Skip(page * pageSize)
            .Take(pageSize)
            .ToListAsync(cancellationToken);

        return new PagedResult<Event>
        {
            Items = items,
            TotalCount = totalCount,
            Page = page,
            PageSize = pageSize
        };
    }
}
