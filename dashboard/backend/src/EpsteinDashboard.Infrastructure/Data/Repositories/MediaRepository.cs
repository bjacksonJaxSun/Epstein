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
        bool excludeDocumentScans = false,
        CancellationToken cancellationToken = default)
    {
        var query = DbSet.AsNoTracking().AsQueryable();

        if (!string.IsNullOrEmpty(mediaType))
            query = query.Where(m => m.MediaType == mediaType);

        // Filter out document scans (images extracted from PDFs)
        if (excludeDocumentScans)
            query = query.Where(m => m.Caption == null || !m.Caption.StartsWith("Extracted from EFTA"));

        var totalCount = await query.CountAsync(cancellationToken);

        if (!string.IsNullOrEmpty(sortBy))
            query = ApplySort(query, sortBy, sortDirection);
        else
            query = query.OrderBy(m => m.MediaFileId);

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

    public async Task<MediaPositionResult?> GetMediaPositionAsync(long id, int pageSize, string? mediaType = null, bool excludeDocumentScans = false, CancellationToken cancellationToken = default)
    {
        var query = DbSet.AsNoTracking().AsQueryable();

        if (!string.IsNullOrEmpty(mediaType))
            query = query.Where(m => m.MediaType == mediaType);

        // Filter out document scans (images extracted from PDFs)
        if (excludeDocumentScans)
            query = query.Where(m => m.Caption == null || !m.Caption.StartsWith("Extracted from EFTA"));

        // Default sort is by MediaFileId ascending
        query = query.OrderBy(m => m.MediaFileId);

        var totalCount = await query.CountAsync(cancellationToken);

        // Count how many items come before this ID
        var position = await query.CountAsync(m => m.MediaFileId < id, cancellationToken);

        // Verify the item exists
        var exists = await query.AnyAsync(m => m.MediaFileId == id, cancellationToken);
        if (!exists)
            return null;

        var page = position / pageSize;
        var indexOnPage = position % pageSize;
        var totalPages = pageSize > 0 ? (int)Math.Ceiling((double)totalCount / pageSize) : 0;

        return new MediaPositionResult
        {
            MediaFileId = id,
            Page = page,
            IndexOnPage = indexOnPage,
            GlobalIndex = position,
            TotalCount = totalCount,
            TotalPages = totalPages
        };
    }
}
