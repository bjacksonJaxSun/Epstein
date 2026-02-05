namespace EpsteinDashboard.Core.Models;

public class SearchRequest
{
    public string Query { get; set; } = string.Empty;
    public int Page { get; set; } = 0;
    public int PageSize { get; set; } = 50;
    public bool Highlight { get; set; } = true;
    public string? DateFrom { get; set; }
    public string? DateTo { get; set; }
    public List<string>? DocumentTypes { get; set; }
}
