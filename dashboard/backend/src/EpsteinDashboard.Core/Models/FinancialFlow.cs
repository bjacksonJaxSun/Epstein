namespace EpsteinDashboard.Core.Models;

public class SankeyNode
{
    public string Id { get; set; } = string.Empty;
    public string Label { get; set; } = string.Empty;
    public string? Type { get; set; }
}

public class SankeyLink
{
    public string Source { get; set; } = string.Empty;
    public string Target { get; set; } = string.Empty;
    public decimal Value { get; set; }
    public int TransactionCount { get; set; } = 1;
    public string? Currency { get; set; }
    public string? Purpose { get; set; }
}

public class FinancialFlow
{
    public List<SankeyNode> Nodes { get; set; } = new();
    public List<SankeyLink> Links { get; set; } = new();
    public decimal TotalAmount { get; set; }
    public string? PrimaryCurrency { get; set; }
}
