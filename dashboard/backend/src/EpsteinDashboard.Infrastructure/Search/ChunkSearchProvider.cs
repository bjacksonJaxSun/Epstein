using System.Text.RegularExpressions;
using Dapper;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Microsoft.Data.Sqlite;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;

namespace EpsteinDashboard.Infrastructure.Search;

/// <summary>
/// Provides chunk-level search using FTS5 on document chunks.
/// Enables context-preserving search results for RAG applications.
/// </summary>
public partial class ChunkSearchProvider : IChunkSearchService
{
    private readonly string _connectionString;
    private readonly ILogger<ChunkSearchProvider> _logger;

    public ChunkSearchProvider(
        IConfiguration configuration,
        ILogger<ChunkSearchProvider> logger)
    {
        _connectionString = configuration.GetConnectionString("EpsteinDb")
            ?? throw new InvalidOperationException("EpsteinDb connection string not configured.");
        _logger = logger;
    }

    public async Task<bool> IsAvailableAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            await using var connection = new SqliteConnection(_connectionString);
            await connection.OpenAsync(cancellationToken);

            var exists = await connection.QuerySingleOrDefaultAsync<int>(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='document_chunks'");

            return exists > 0;
        }
        catch
        {
            return false;
        }
    }

    public async Task<ChunkSearchStats> GetStatsAsync(CancellationToken cancellationToken = default)
    {
        await using var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        var stats = new ChunkSearchStats();

        // Check table availability
        var chunksExist = await connection.QuerySingleOrDefaultAsync<int>(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='document_chunks'");
        var chunksFtsExist = await connection.QuerySingleOrDefaultAsync<int>(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='chunks_fts'");
        var embeddingsExist = await connection.QuerySingleOrDefaultAsync<int>(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='chunk_embeddings'");

        stats.FtsAvailable = chunksFtsExist > 0;
        stats.VectorSearchAvailable = embeddingsExist > 0;

        if (chunksExist == 0)
        {
            return stats;
        }

        // Get counts
        stats.TotalDocuments = await connection.QuerySingleAsync<long>(
            "SELECT COUNT(*) FROM documents");

        stats.DocumentsWithChunks = await connection.QuerySingleAsync<long>(
            "SELECT COUNT(DISTINCT document_id) FROM document_chunks");

        stats.TotalChunks = await connection.QuerySingleAsync<long>(
            "SELECT COUNT(*) FROM document_chunks");

        if (stats.DocumentsWithChunks > 0)
        {
            stats.AverageChunksPerDocument = (double)stats.TotalChunks / stats.DocumentsWithChunks;
        }

        if (embeddingsExist > 0)
        {
            stats.ChunksWithEmbeddings = await connection.QuerySingleAsync<long>(
                "SELECT COUNT(*) FROM chunk_embeddings");
        }

        return stats;
    }

    public async Task<PagedResult<ChunkSearchResult>> SearchChunksAsync(
        ChunkSearchRequest request,
        CancellationToken cancellationToken = default)
    {
        var sanitizedQuery = SanitizeFts5Query(request.Query);
        if (string.IsNullOrWhiteSpace(sanitizedQuery))
        {
            return new PagedResult<ChunkSearchResult>
            {
                Items = Array.Empty<ChunkSearchResult>(),
                TotalCount = 0,
                Page = request.Page,
                PageSize = request.PageSize
            };
        }

        await using var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        // Check if chunks FTS table exists
        var ftsExists = await connection.QuerySingleOrDefaultAsync<int>(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='chunks_fts'");

        if (ftsExists == 0)
        {
            _logger.LogWarning("Chunks FTS table not available. Run chunking migration first.");
            return new PagedResult<ChunkSearchResult>
            {
                Items = Array.Empty<ChunkSearchResult>(),
                TotalCount = 0,
                Page = request.Page,
                PageSize = request.PageSize
            };
        }

        return await SearchWithChunkFts5(connection, request, sanitizedQuery, cancellationToken);
    }

    private async Task<PagedResult<ChunkSearchResult>> SearchWithChunkFts5(
        SqliteConnection connection,
        ChunkSearchRequest request,
        string sanitizedQuery,
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

        // Count query
        var countSql = $@"
            SELECT COUNT(*)
            FROM chunks_fts
            JOIN document_chunks c ON c.rowid = chunks_fts.rowid
            JOIN documents d ON d.document_id = c.document_id
            WHERE chunks_fts MATCH @Query{filterClause}";

        var totalCount = await connection.QuerySingleAsync<int>(countSql, parameters);

        // Select context columns based on request
        var contextColumns = request.IncludeContext
            ? "c.preceding_context AS PrecedingContext, c.following_context AS FollowingContext,"
            : "";

        // Search query with snippet highlighting
        var searchSql = $@"
            SELECT
                c.chunk_id AS ChunkId,
                c.document_id AS DocumentId,
                c.efta_number AS EftaNumber,
                c.chunk_index AS ChunkIndex,
                c.chunk_text AS ChunkText,
                snippet(chunks_fts, 2, '<mark>', '</mark>', '...', 64) AS Snippet,
                c.page_number AS PageNumber,
                c.has_redaction AS HasRedaction,
                {contextColumns}
                rank AS RelevanceScore,
                d.document_title AS DocumentTitle,
                d.document_date AS DocumentDate,
                d.document_type AS DocumentType
            FROM chunks_fts
            JOIN document_chunks c ON c.rowid = chunks_fts.rowid
            JOIN documents d ON d.document_id = c.document_id
            WHERE chunks_fts MATCH @Query{filterClause}
            ORDER BY rank
            LIMIT @PageSize OFFSET @Offset";

        var results = await connection.QueryAsync<ChunkSearchResult>(searchSql, parameters);

        return new PagedResult<ChunkSearchResult>
        {
            Items = results.ToList(),
            TotalCount = totalCount,
            Page = request.Page,
            PageSize = request.PageSize
        };
    }

    public async Task<IReadOnlyList<ChunkSearchResult>> GetDocumentChunksAsync(
        long documentId,
        CancellationToken cancellationToken = default)
    {
        await using var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        var sql = @"
            SELECT
                c.chunk_id AS ChunkId,
                c.document_id AS DocumentId,
                c.efta_number AS EftaNumber,
                c.chunk_index AS ChunkIndex,
                c.chunk_text AS ChunkText,
                c.page_number AS PageNumber,
                c.has_redaction AS HasRedaction,
                c.preceding_context AS PrecedingContext,
                c.following_context AS FollowingContext,
                1.0 AS RelevanceScore,
                d.document_title AS DocumentTitle,
                d.document_date AS DocumentDate,
                d.document_type AS DocumentType
            FROM document_chunks c
            JOIN documents d ON d.document_id = c.document_id
            WHERE c.document_id = @DocumentId
            ORDER BY c.chunk_index";

        var results = await connection.QueryAsync<ChunkSearchResult>(sql, new { DocumentId = documentId });
        return results.ToList();
    }

    private static string SanitizeFts5Query(string query)
    {
        if (string.IsNullOrWhiteSpace(query)) return string.Empty;

        // Remove special FTS5 characters
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
