namespace EpsteinDashboard.Core.Models;

public class PagedResult<T>
{
    public IReadOnlyList<T> Items { get; set; } = Array.Empty<T>();
    public int TotalCount { get; set; }
    public int Page { get; set; }
    public int PageSize { get; set; }
    public int TotalPages => PageSize > 0 ? (int)Math.Ceiling((double)TotalCount / PageSize) : 0;
    public bool HasPrevious => Page > 0;
    public bool HasNext => Page < TotalPages - 1;
}

public class MediaPositionResult
{
    public long MediaFileId { get; set; }
    public int Page { get; set; }
    public int IndexOnPage { get; set; }
    public int GlobalIndex { get; set; }
    public int TotalCount { get; set; }
    public int TotalPages { get; set; }
}
