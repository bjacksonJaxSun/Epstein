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

    public async Task<IReadOnlyList<Document>> GetDocumentsAsync(long organizationId, CancellationToken cancellationToken = default)
    {
        // Get documents where this organization was first mentioned
        var org = await DbSet.AsNoTracking()
            .Include(o => o.FirstMentionedInDocument)
            .FirstOrDefaultAsync(o => o.OrganizationId == organizationId, cancellationToken);

        if (org?.FirstMentionedInDocument != null)
        {
            return new List<Document> { org.FirstMentionedInDocument };
        }

        return new List<Document>();
    }

    public async Task<IReadOnlyList<FinancialTransaction>> GetFinancialTransactionsAsync(long organizationId, CancellationToken cancellationToken = default)
    {
        return await Context.Set<FinancialTransaction>()
            .AsNoTracking()
            .Include(t => t.FromPerson)
            .Include(t => t.ToPerson)
            .Include(t => t.FromOrganization)
            .Include(t => t.ToOrganization)
            .Where(t => t.FromOrganizationId == organizationId || t.ToOrganizationId == organizationId)
            .OrderByDescending(t => t.TransactionDate)
            .Take(50)
            .ToListAsync(cancellationToken);
    }

    public async Task<IReadOnlyList<Person>> GetRelatedPeopleAsync(long organizationId, CancellationToken cancellationToken = default)
    {
        // Get people related through financial transactions - split into two queries to avoid EF Core translation issues
        var fromPersonIds = await Context.Set<FinancialTransaction>()
            .AsNoTracking()
            .Where(t => t.FromOrganizationId == organizationId && t.FromPersonId.HasValue)
            .Select(t => t.FromPersonId!.Value)
            .Distinct()
            .ToListAsync(cancellationToken);

        var toPersonIds = await Context.Set<FinancialTransaction>()
            .AsNoTracking()
            .Where(t => t.ToOrganizationId == organizationId && t.ToPersonId.HasValue)
            .Select(t => t.ToPersonId!.Value)
            .Distinct()
            .ToListAsync(cancellationToken);

        var allPersonIds = fromPersonIds.Union(toPersonIds).Distinct().ToList();

        if (allPersonIds.Count == 0)
            return new List<Person>();

        return await Context.Set<Person>()
            .AsNoTracking()
            .Where(p => allPersonIds.Contains(p.PersonId))
            .OrderBy(p => p.FullName)
            .Take(50)
            .ToListAsync(cancellationToken);
    }
}
