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
        var sanitizedQuery = SanitizeFts5Query(request.Query);
        if (string.IsNullOrWhiteSpace(sanitizedQuery))
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

        // Check if FTS5 table exists, fall back to LIKE search if not
        var ftsExists = await connection.QuerySingleOrDefaultAsync<int>(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='documents_fts'");

        if (ftsExists > 0)
        {
            return await SearchWithFts5(connection, request, sanitizedQuery, cancellationToken);
        }

        return await SearchWithLike(connection, request, cancellationToken);
    }

    private async Task<PagedResult<SearchResult>> SearchWithFts5(
        NpgsqlConnection connection, SearchRequest request, string sanitizedQuery,
        CancellationToken cancellationToken)
    {
        // Build filter conditions
        var filterConditions = new List<string>();
        var parameters = new DynamicParameters();
        parameters.Add("Query", sanitizedQuery);
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
            filterConditions.Add("d.document_type IN @DocumentTypes");
            parameters.Add("DocumentTypes", request.DocumentTypes);
        }

        var filterClause = filterConditions.Count > 0
            ? " AND " + string.Join(" AND ", filterConditions)
            : "";

        var countSql = $@"
            SELECT COUNT(*)
            FROM documents_fts
            JOIN documents d ON d.document_id = documents_fts.rowid
            WHERE documents_fts MATCH @Query{filterClause}";

        var totalCount = await connection.QuerySingleAsync<int>(countSql, parameters);

        // Use snippet on cleaned_text (column 3) if available, otherwise full_text (column 2)
        var searchSql = $@"
            SELECT
                d.document_id AS DocumentId,
                d.efta_number AS EftaNumber,
                d.document_title AS Title,
                COALESCE(
                    snippet(documents_fts, 3, '<mark>', '</mark>', '...', 64),
                    snippet(documents_fts, 2, '<mark>', '</mark>', '...', 64)
                ) AS Snippet,
                rank AS RelevanceScore,
                d.document_date AS DocumentDate,
                d.document_type AS DocumentType,
                d.page_count AS PageCount,
                d.is_redacted AS IsRedacted
            FROM documents_fts
            JOIN documents d ON d.document_id = documents_fts.rowid
            WHERE documents_fts MATCH @Query{filterClause}
            ORDER BY rank
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

    private async Task<PagedResult<SearchResult>> SearchWithLike(
        NpgsqlConnection connection, SearchRequest request,
        CancellationToken cancellationToken)
    {
        var likePattern = $"%{request.Query}%";

        var countSql = @"
            SELECT COUNT(*)
            FROM documents
            WHERE full_text LIKE @Pattern
                OR document_title LIKE @Pattern
                OR subject LIKE @Pattern";

        var totalCount = await connection.QuerySingleAsync<int>(countSql, new { Pattern = likePattern });

        var searchSql = @"
            SELECT
                document_id AS DocumentId,
                efta_number AS EftaNumber,
                document_title AS Title,
                SUBSTR(full_text, MAX(1, INSTR(LOWER(full_text), LOWER(@Query)) - 100), 250) AS Snippet,
                1.0 AS RelevanceScore,
                document_date AS DocumentDate,
                document_type AS DocumentType
            FROM documents
            WHERE full_text LIKE @Pattern
                OR document_title LIKE @Pattern
                OR subject LIKE @Pattern
            ORDER BY document_date DESC
            LIMIT @PageSize OFFSET @Offset";

        var results = await connection.QueryAsync<SearchResult>(searchSql, new
        {
            Query = request.Query,
            Pattern = likePattern,
            PageSize = request.PageSize,
            Offset = request.Page * request.PageSize
        });

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
            WHERE document_title LIKE @Pattern
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

    private static string SanitizeFts5Query(string query)
    {
        if (string.IsNullOrWhiteSpace(query)) return string.Empty;

        // Remove special FTS5 characters that could cause syntax errors
        var sanitized = FtsSpecialCharsRegex().Replace(query, " ");

        // Collapse whitespace
        sanitized = MultipleSpacesRegex().Replace(sanitized.Trim(), " ");

        if (string.IsNullOrWhiteSpace(sanitized)) return string.Empty;

        // Wrap each word in quotes for exact matching
        var words = sanitized.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        return string.Join(" ", words.Select(w => $"\"{w}\""));
    }

    [GeneratedRegex(@"[""'\(\)\*\:\;\!\?\+\-\^~\{\}\[\]\\\/]")]
    private static partial Regex FtsSpecialCharsRegex();

    [GeneratedRegex(@"\s+")]
    private static partial Regex MultipleSpacesRegex();
}
