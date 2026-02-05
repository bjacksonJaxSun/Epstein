using EpsteinDashboard.Core.Models;

namespace EpsteinDashboard.Core.Interfaces;

public interface ISearchService
{
    Task<PagedResult<SearchResult>> SearchAsync(SearchRequest request, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<string>> SuggestAsync(string query, int limit = 10, CancellationToken cancellationToken = default);
}
