using EpsteinDashboard.Core.Entities;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Microsoft.EntityFrameworkCore;

namespace EpsteinDashboard.Infrastructure.Data.Repositories;

public class DocumentRepository : BaseRepository<Document>, IDocumentRepository
{
    public DocumentRepository(EpsteinDbContext context) : base(context)
    {
    }

    public async Task<Document?> GetByEftaNumberAsync(string eftaNumber, CancellationToken cancellationToken = default)
    {
        return await DbSet.AsNoTracking()
            .FirstOrDefaultAsync(d => d.EftaNumber == eftaNumber, cancellationToken);
    }

    public async Task<PagedResult<Document>> GetFilteredAsync(
        int page, int pageSize, string? documentType = null,
        string? dateFrom = null, string? dateTo = null,
        string? sortBy = null, string? sortDirection = null,
        CancellationToken cancellationToken = default)
    {
        var query = DbSet.AsNoTracking();

        if (!string.IsNullOrEmpty(documentType))
            query = query.Where(d => d.DocumentType == documentType);

        if (!string.IsNullOrEmpty(dateFrom))
            query = query.Where(d => string.Compare(d.DocumentDate, dateFrom) >= 0);

        if (!string.IsNullOrEmpty(dateTo))
            query = query.Where(d => string.Compare(d.DocumentDate, dateTo) <= 0);

        var totalCount = await query.CountAsync(cancellationToken);

        if (!string.IsNullOrEmpty(sortBy))
            query = ApplySort(query, sortBy, sortDirection);

        var items = await query
            .Skip(page * pageSize)
            .Take(pageSize)
            .ToListAsync(cancellationToken);

        return new PagedResult<Document>
        {
            Items = items,
            TotalCount = totalCount,
            Page = page,
            PageSize = pageSize
        };
    }

    public async Task<Document?> GetWithEntitiesAsync(long id, CancellationToken cancellationToken = default)
    {
        return await DbSet.AsNoTracking()
            .Include(d => d.MentionedPersons)
            .Include(d => d.MentionedOrganizations)
            .Include(d => d.MentionedLocations)
            .Include(d => d.SourceRelationships)
            .Include(d => d.SourceEvents)
            .Include(d => d.SourceCommunications)
            .Include(d => d.SourceTransactions)
            .Include(d => d.SourceEvidenceItems)
            .FirstOrDefaultAsync(d => d.DocumentId == id, cancellationToken);
    }

    public async Task<IReadOnlyList<string>> GetDocumentTypesAsync(CancellationToken cancellationToken = default)
    {
        return await DbSet.AsNoTracking()
            .Where(d => d.DocumentType != null)
            .Select(d => d.DocumentType!)
            .Distinct()
            .OrderBy(t => t)
            .ToListAsync(cancellationToken);
    }
}
