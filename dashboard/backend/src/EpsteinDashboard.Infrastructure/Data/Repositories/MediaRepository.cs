using EpsteinDashboard.Core.Entities;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Microsoft.EntityFrameworkCore;

namespace EpsteinDashboard.Infrastructure.Data.Repositories;

public class MediaRepository : BaseRepository<MediaFile>, IMediaRepository
{
    public MediaRepository(EpsteinDbContext context) : base(context)
    {
    }

    public async Task<MediaFile?> GetWithAnalysisAsync(long id, CancellationToken cancellationToken = default)
    {
        return await DbSet.AsNoTracking()
            .Include(m => m.Analyses)
            .Include(m => m.TaggedPersons).ThenInclude(tp => tp.Person)
            .Include(m => m.VisualEntities)
            .Include(m => m.Location)
            .Include(m => m.EvidenceItem)
            .FirstOrDefaultAsync(m => m.MediaFileId == id, cancellationToken);
    }

    public async Task<PagedResult<MediaFile>> GetFilteredAsync(
        int page, int pageSize, string? mediaType = null,
        string? sortBy = null, string? sortDirection = null,
        CancellationToken cancellationToken = default)
    {
        var query = DbSet.AsNoTracking().AsQueryable();

        if (!string.IsNullOrEmpty(mediaType))
            query = query.Where(m => m.MediaType == mediaType);

        var totalCount = await query.CountAsync(cancellationToken);

        if (!string.IsNullOrEmpty(sortBy))
            query = ApplySort(query, sortBy, sortDirection);

        var items = await query
            .Skip(page * pageSize)
            .Take(pageSize)
            .ToListAsync(cancellationToken);

        return new PagedResult<MediaFile>
        {
            Items = items,
            TotalCount = totalCount,
            Page = page,
            PageSize = pageSize
        };
    }

    public async Task<IReadOnlyList<ImageAnalysis>> GetAnalysesForMediaAsync(long mediaFileId, CancellationToken cancellationToken = default)
    {
        return await Context.ImageAnalyses.AsNoTracking()
            .Where(a => a.MediaFileId == mediaFileId)
            .ToListAsync(cancellationToken);
    }
}
