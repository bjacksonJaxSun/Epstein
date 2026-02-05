using EpsteinDashboard.Core.Models;

namespace EpsteinDashboard.Application.DTOs;

public class FinancialTransactionDto
{
    public long TransactionId { get; set; }
    public string? TransactionType { get; set; }
    public decimal? Amount { get; set; }
    public string? Currency { get; set; }
    public string? FromName { get; set; }
    public string? ToName { get; set; }
    public string? TransactionDate { get; set; }
    public string? Purpose { get; set; }
    public string? ReferenceNumber { get; set; }
    public string? BankName { get; set; }
    public string? CreatedAt { get; set; }
}

public class FinancialFlowDto
{
    public List<SankeyNode> Nodes { get; set; } = new();
    public List<SankeyLink> Links { get; set; } = new();
    public decimal TotalAmount { get; set; }
    public string? PrimaryCurrency { get; set; }
}

public class SankeyDataDto
{
    public List<SankeyNodeDto> Nodes { get; set; } = new();
    public List<SankeyLinkDto> Links { get; set; } = new();
}

public class SankeyNodeDto
{
    public string Id { get; set; } = string.Empty;
    public string Label { get; set; } = string.Empty;
    public string? Type { get; set; }
}

public class SankeyLinkDto
{
    public string Source { get; set; } = string.Empty;
    public string Target { get; set; } = string.Empty;
    public decimal Value { get; set; }
    public string? Currency { get; set; }
    public string? Purpose { get; set; }
}
