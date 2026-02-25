using System.Text.RegularExpressions;
using Dapper;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Npgsql;
using Microsoft.Extensions.Configuration;

namespace EpsteinDashboard.Infrastructure.Search;

public partial class Fts5SearchProvider : ISearchService
{
    private readonly string _connectionString;

    public Fts5SearchProvider(IConfiguration configuration)
    {
        _connectionString = configuration.GetConnectionString("EpsteinDb")
            ?? throw new InvalidOperationException("EpsteinDb connection string not configured.");
    }

    public async Task<PagedResult<SearchResult>> SearchAsync(SearchRequest request, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(request.Query))
        {
            return new PagedResult<SearchResult>
            {
                Items = Array.Empty<SearchResult>(),
                TotalCount = 0,
                Page = request.Page,
                PageSize = request.PageSize
            };
        }

        await using var connection = new NpgsqlConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        // Try strict AND matching first (all terms must appear)
        var result = await SearchWithFts(connection, request, useOrMatching: false, cancellationToken);

        // If AND returns 0 results, fall back to OR matching for better recall
        if (result.TotalCount == 0)
        {
            result = await SearchWithFts(connection, request, useOrMatching: true, cancellationToken);
        }

        return result;
    }

    private async Task<PagedResult<SearchResult>> SearchWithFts(
        NpgsqlConnection connection, SearchRequest request, bool useOrMatching,
        CancellationToken cancellationToken)
    {
        // plainto_tsquery safely parses the query into lexemes with AND logic.
        // For OR matching, convert AND operators to OR:
        //   "visit & littl & st & jame" -> "visit | littl | st | jame"
        var tsqueryExpr = useOrMatching
            ? "replace(plainto_tsquery('english', @Query)::text, ' & ', ' | ')::tsquery"
            : "plainto_tsquery('english', @Query)";

        var filterConditions = new List<string>
        {
            $"to_tsvector('english', COALESCE(d.full_text, '')) @@ {tsqueryExpr}"
        };
        var parameters = new DynamicParameters();
        parameters.Add("Query", request.Query);
        parameters.Add("PageSize", request.PageSize);
        parameters.Add("Offset", request.Page * request.PageSize);

        if (!string.IsNullOrEmpty(request.DateFrom))
        {
            filterConditions.Add("d.document_date >= @DateFrom");
            parameters.Add("DateFrom", request.DateFrom);
        }
        if (!string.IsNullOrEmpty(request.DateTo))
        {
            filterConditions.Add("d.document_date <= @DateTo");
            parameters.Add("DateTo", request.DateTo);
        }
        if (request.DocumentTypes?.Any() == true)
        {
            filterConditions.Add("d.document_type = ANY(@DocumentTypes)");
            parameters.Add("DocumentTypes", request.DocumentTypes.ToArray());
        }

        var filterClause = " WHERE " + string.Join(" AND ", filterConditions);

        var countSql = $@"
            SELECT COUNT(*)
            FROM documents d
            {filterClause}";

        var totalCount = await connection.QuerySingleAsync<int>(countSql, parameters);

        var searchSql = $@"
            SELECT
                d.document_id AS DocumentId,
                d.efta_number AS EftaNumber,
                d.document_title AS Title,
                ts_headline('english', COALESCE(d.full_text, ''), {tsqueryExpr},
                    'MaxWords=50, MinWords=20, StartSel=<mark>, StopSel=</mark>') AS Snippet,
                ts_rank(to_tsvector('english', COALESCE(d.full_text, '')), {tsqueryExpr})::float8 AS RelevanceScore,
                d.document_date AS DocumentDate,
                d.document_type AS DocumentType,
                d.page_count AS PageCount,
                d.is_redacted AS IsRedacted
            FROM documents d
            {filterClause}
            ORDER BY RelevanceScore DESC
            LIMIT @PageSize OFFSET @Offset";

        var results = await connection.QueryAsync<SearchResult>(searchSql, parameters);

        return new PagedResult<SearchResult>
        {
            Items = results.ToList(),
            TotalCount = totalCount,
            Page = request.Page,
            PageSize = request.PageSize
        };
    }

    public async Task<IReadOnlyList<string>> SuggestAsync(string query, int limit = 10, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(query) || query.Length < 2)
            return Array.Empty<string>();

        await using var connection = new NpgsqlConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        var sql = @"
            SELECT DISTINCT document_title
            FROM documents
            WHERE document_title ILIKE @Pattern
            AND document_title IS NOT NULL
            ORDER BY document_title
            LIMIT @Limit";

        var results = await connection.QueryAsync<string>(sql, new
        {
            Pattern = $"%{query}%",
            Limit = limit
        });

        return results.ToList();
    }

    [GeneratedRegex(@"[""'\(\)\*\:\;\!\?\+\-\^~\{\}\[\]\\\/]")]
    private static partial Regex FtsSpecialCharsRegex();

    [GeneratedRegex(@"\s+")]
    private static partial Regex MultipleSpacesRegex();
}
