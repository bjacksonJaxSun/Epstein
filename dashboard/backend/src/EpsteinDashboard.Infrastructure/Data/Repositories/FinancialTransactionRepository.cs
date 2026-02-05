using EpsteinDashboard.Core.Entities;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Microsoft.EntityFrameworkCore;

namespace EpsteinDashboard.Infrastructure.Data.Repositories;

public class FinancialTransactionRepository : BaseRepository<FinancialTransaction>, IFinancialTransactionRepository
{
    public FinancialTransactionRepository(EpsteinDbContext context) : base(context)
    {
    }

    public async Task<PagedResult<FinancialTransaction>> GetFilteredAsync(
        int page, int pageSize, string? transactionType = null,
        string? dateFrom = null, string? dateTo = null,
        string? sortBy = null, string? sortDirection = null,
        CancellationToken cancellationToken = default)
    {
        var query = DbSet.AsNoTracking()
            .Include(t => t.FromPerson)
            .Include(t => t.ToPerson)
            .Include(t => t.FromOrganization)
            .Include(t => t.ToOrganization)
            .AsQueryable();

        if (!string.IsNullOrEmpty(transactionType))
            query = query.Where(t => t.TransactionType == transactionType);

        if (!string.IsNullOrEmpty(dateFrom))
            query = query.Where(t => string.Compare(t.TransactionDate, dateFrom) >= 0);

        if (!string.IsNullOrEmpty(dateTo))
            query = query.Where(t => string.Compare(t.TransactionDate, dateTo) <= 0);

        var totalCount = await query.CountAsync(cancellationToken);

        if (!string.IsNullOrEmpty(sortBy))
            query = ApplySort(query, sortBy, sortDirection);

        var items = await query
            .Skip(page * pageSize)
            .Take(pageSize)
            .ToListAsync(cancellationToken);

        return new PagedResult<FinancialTransaction>
        {
            Items = items,
            TotalCount = totalCount,
            Page = page,
            PageSize = pageSize
        };
    }

    public async Task<FinancialFlow> GetFlowsAsync(CancellationToken cancellationToken = default)
    {
        var transactions = await DbSet.AsNoTracking()
            .Include(t => t.FromPerson)
            .Include(t => t.ToPerson)
            .Include(t => t.FromOrganization)
            .Include(t => t.ToOrganization)
            .Where(t => t.Amount != null && t.Amount > 0)
            .ToListAsync(cancellationToken);

        var nodeDict = new Dictionary<string, SankeyNode>();
        var linkDict = new Dictionary<string, SankeyLink>();

        foreach (var t in transactions)
        {
            string sourceId;
            string sourceLabel;
            string sourceType;

            if (t.FromPersonId.HasValue && t.FromPerson != null)
            {
                sourceId = $"person-{t.FromPersonId}";
                sourceLabel = t.FromPerson.FullName;
                sourceType = "person";
            }
            else if (t.FromOrganizationId.HasValue && t.FromOrganization != null)
            {
                sourceId = $"org-{t.FromOrganizationId}";
                sourceLabel = t.FromOrganization.OrganizationName;
                sourceType = "organization";
            }
            else continue;

            string targetId;
            string targetLabel;
            string targetType;

            if (t.ToPersonId.HasValue && t.ToPerson != null)
            {
                targetId = $"person-{t.ToPersonId}";
                targetLabel = t.ToPerson.FullName;
                targetType = "person";
            }
            else if (t.ToOrganizationId.HasValue && t.ToOrganization != null)
            {
                targetId = $"org-{t.ToOrganizationId}";
                targetLabel = t.ToOrganization.OrganizationName;
                targetType = "organization";
            }
            else continue;

            // Skip self-referential links (same source and target) - they crash Sankey diagrams
            if (sourceId == targetId)
                continue;

            if (!nodeDict.ContainsKey(sourceId))
                nodeDict[sourceId] = new SankeyNode { Id = sourceId, Label = sourceLabel, Type = sourceType };
            if (!nodeDict.ContainsKey(targetId))
                nodeDict[targetId] = new SankeyNode { Id = targetId, Label = targetLabel, Type = targetType };

            // Aggregate links by source-target pair
            var linkKey = $"{sourceId}|{targetId}";
            if (linkDict.TryGetValue(linkKey, out var existingLink))
            {
                existingLink.Value += t.Amount ?? 0;
                existingLink.TransactionCount++;
            }
            else
            {
                linkDict[linkKey] = new SankeyLink
                {
                    Source = sourceId,
                    Target = targetId,
                    Value = t.Amount ?? 0,
                    TransactionCount = 1,
                    Currency = t.Currency,
                    Purpose = t.Purpose
                };
            }
        }

        var totalAmount = transactions.Sum(t => t.Amount ?? 0);
        var primaryCurrency = transactions
            .Where(t => t.Currency != null)
            .GroupBy(t => t.Currency)
            .OrderByDescending(g => g.Count())
            .Select(g => g.Key)
            .FirstOrDefault();

        return new FinancialFlow
        {
            Nodes = nodeDict.Values.ToList(),
            Links = linkDict.Values.ToList(),
            TotalAmount = totalAmount,
            PrimaryCurrency = primaryCurrency
        };
    }

    public async Task<FinancialSummary> GetSummaryAsync(CancellationToken cancellationToken = default)
    {
        var transactions = await DbSet.AsNoTracking().ToListAsync(cancellationToken);

        var summary = new FinancialSummary
        {
            TotalTransactions = transactions.Count,
            TotalAmount = transactions.Sum(t => t.Amount ?? 0),
            PrimaryCurrency = transactions
                .Where(t => t.Currency != null)
                .GroupBy(t => t.Currency)
                .OrderByDescending(g => g.Count())
                .Select(g => g.Key)
                .FirstOrDefault()
        };

        foreach (var group in transactions.GroupBy(t => t.TransactionType ?? "Unknown"))
        {
            summary.AmountByType[group.Key] = group.Sum(t => t.Amount ?? 0);
            summary.CountByType[group.Key] = group.Count();
        }

        return summary;
    }
}
