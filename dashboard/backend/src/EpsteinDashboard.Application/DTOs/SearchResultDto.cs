namespace EpsteinDashboard.Application.DTOs;

public class SearchResultDto
{
    public long DocumentId { get; set; }
    public string? EftaNumber { get; set; }
    public string? Title { get; set; }
    public string? Snippet { get; set; }
    public double RelevanceScore { get; set; }
    public string? DocumentDate { get; set; }
    public string? DocumentType { get; set; }
}
