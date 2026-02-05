using EpsteinDashboard.Core.Entities;
using EpsteinDashboard.Core.Models;

namespace EpsteinDashboard.Core.Interfaces;

public interface IFinancialTransactionRepository : IRepository<FinancialTransaction>
{
    Task<PagedResult<FinancialTransaction>> GetFilteredAsync(int page, int pageSize, string? transactionType = null, string? dateFrom = null, string? dateTo = null, string? sortBy = null, string? sortDirection = null, CancellationToken cancellationToken = default);
    Task<FinancialFlow> GetFlowsAsync(CancellationToken cancellationToken = default);
    Task<FinancialSummary> GetSummaryAsync(CancellationToken cancellationToken = default);
}

public class FinancialSummary
{
    public int TotalTransactions { get; set; }
    public decimal TotalAmount { get; set; }
    public string? PrimaryCurrency { get; set; }
    public Dictionary<string, decimal> AmountByType { get; set; } = new();
    public Dictionary<string, int> CountByType { get; set; } = new();
}
