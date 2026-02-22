using System.Text.RegularExpressions;
using Dapper;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Npgsql;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;

namespace EpsteinDashboard.Infrastructure.Search;

/// <summary>
/// Provides chunk-level semantic search using PostgreSQL full-text search
/// and pgvector for vector similarity search on document chunks.
/// </summary>
public partial class ChunkSearchProvider : IChunkSearchService
{
    private readonly string _connectionString;
    private readonly ILogger<ChunkSearchProvider> _logger;

    // The stored embeddings use all-MiniLM-L6-v2 (384 dimensions)
    private const int EmbeddingDimensions = 384;

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
            await using var connection = new NpgsqlConnection(_connectionString);
            await connection.OpenAsync(cancellationToken);

            var exists = await connection.QuerySingleOrDefaultAsync<int>(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'document_chunks'");

            return exists > 0;
        }
        catch
        {
            return false;
        }
    }

    public async Task<ChunkSearchStats> GetStatsAsync(CancellationToken cancellationToken = default)
    {
        await using var connection = new NpgsqlConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        var stats = new ChunkSearchStats();

        var chunksExist = await connection.QuerySingleOrDefaultAsync<int>(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'document_chunks'");

        if (chunksExist == 0)
        {
            return stats;
        }

        stats.FtsAvailable = true; // PostgreSQL native FTS always available

        // Check if pgvector extension is active and embeddings exist
        var vectorExtInstalled = await connection.QuerySingleOrDefaultAsync<int>(
            "SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'");
        if (vectorExtInstalled > 0)
        {
            var embeddingCount = await connection.QuerySingleOrDefaultAsync<long>(
                "SELECT COUNT(*) FROM document_chunks WHERE embedding_vector IS NOT NULL");
            stats.VectorSearchAvailable = embeddingCount > 0;
            stats.ChunksWithEmbeddings = embeddingCount;
        }

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

        return stats;
    }

    public async Task<PagedResult<ChunkSearchResult>> SearchChunksAsync(
        ChunkSearchRequest request,
        CancellationToken cancellationToken = default)
    {
        await using var connection = new NpgsqlConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        // Use vector search if embedding provided and dimensions match
        bool useVector = request.UseVectorSearch
            && request.QueryEmbedding != null
            && request.QueryEmbedding.Length == EmbeddingDimensions;

        if (useVector)
        {
            _logger.LogInformation("Using pgvector similarity search for query: {Query}", request.Query);
            return await SearchWithVector(connection, request, cancellationToken);
        }

        _logger.LogInformation("Using PostgreSQL full-text search for query: {Query}", request.Query);
        return await SearchWithFts(connection, request, cancellationToken);
    }

    private async Task<PagedResult<ChunkSearchResult>> SearchWithVector(
        NpgsqlConnection connection,
        ChunkSearchRequest request,
        CancellationToken cancellationToken)
    {
        // Format vector as PostgreSQL literal
        var vectorLiteral = "[" + string.Join(",", request.QueryEmbedding!) + "]";

        var filterConditions = new List<string> { "c.embedding_vector IS NOT NULL" };
        var parameters = new DynamicParameters();
        parameters.Add("PageSize", request.PageSize);
        parameters.Add("Offset", request.Page * request.PageSize);

        AddDateAndTypeFilters(request, filterConditions, parameters);

        var filterClause = " WHERE " + string.Join(" AND ", filterConditions);

        // Count - approximate for vector search (full count is expensive)
        var totalCount = await connection.QuerySingleAsync<int>(
            $"SELECT COUNT(*) FROM document_chunks c JOIN documents d ON d.document_id = c.document_id{filterClause}",
            parameters);

        var searchSql = $@"
            SELECT
                c.chunk_id::text AS ChunkId,
                c.document_id AS DocumentId,
                d.efta_number AS EftaNumber,
                c.chunk_index AS ChunkIndex,
                c.chunk_text AS ChunkText,
                c.chunk_text AS Snippet,
                NULL::int AS PageNumber,
                false AS HasRedaction,
                NULL::text AS PrecedingContext,
                NULL::text AS FollowingContext,
                (1 - (c.embedding_vector <=> '{vectorLiteral}'::vector))::float8 AS RelevanceScore,
                d.document_title AS DocumentTitle,
                d.document_date AS DocumentDate,
                d.document_type AS DocumentType,
                d.file_path AS FilePath
            FROM document_chunks c
            JOIN documents d ON d.document_id = c.document_id
            {filterClause}
            ORDER BY c.embedding_vector <=> '{vectorLiteral}'::vector
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

    private async Task<PagedResult<ChunkSearchResult>> SearchWithFts(
        NpgsqlConnection connection,
        ChunkSearchRequest request,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(request.Query))
        {
            return new PagedResult<ChunkSearchResult>
            {
                Items = Array.Empty<ChunkSearchResult>(),
                TotalCount = 0,
                Page = request.Page,
                PageSize = request.PageSize
            };
        }

        // Try strict AND matching first (all terms must appear in chunk)
        var result = await ExecuteFtsQuery(connection, request, useOrMatching: false);

        // If AND returns 0 results, fall back to OR matching for better recall
        if (result.TotalCount == 0)
        {
            _logger.LogInformation("AND FTS returned 0 results for '{Query}', falling back to OR matching",
                request.Query);
            result = await ExecuteFtsQuery(connection, request, useOrMatching: true);
        }

        return result;
    }

    private async Task<PagedResult<ChunkSearchResult>> ExecuteFtsQuery(
        NpgsqlConnection connection,
        ChunkSearchRequest request,
        bool useOrMatching)
    {
        // plainto_tsquery safely parses the query into lexemes with AND logic.
        // For OR matching, we convert the AND operators to OR in PostgreSQL:
        //   "visit & littl & st & jame & island" → "visit | littl | st | jame | island"
        // This is SQL-injection safe because plainto_tsquery handles the parsing.
        var tsqueryExpr = useOrMatching
            ? "replace(plainto_tsquery('english', @Query)::text, ' & ', ' | ')::tsquery"
            : "plainto_tsquery('english', @Query)";

        var filterConditions = new List<string>
        {
            $"to_tsvector('english', c.chunk_text) @@ {tsqueryExpr}"
        };
        var parameters = new DynamicParameters();
        parameters.Add("Query", request.Query);
        parameters.Add("PageSize", request.PageSize);
        parameters.Add("Offset", request.Page * request.PageSize);

        AddDateAndTypeFilters(request, filterConditions, parameters);

        var filterClause = " WHERE " + string.Join(" AND ", filterConditions);

        var countSql = $@"
            SELECT COUNT(*)
            FROM document_chunks c
            JOIN documents d ON d.document_id = c.document_id
            {filterClause}";

        var totalCount = await connection.QuerySingleAsync<int>(countSql, parameters);

        var searchSql = $@"
            SELECT
                c.chunk_id::text AS ChunkId,
                c.document_id AS DocumentId,
                d.efta_number AS EftaNumber,
                c.chunk_index AS ChunkIndex,
                c.chunk_text AS ChunkText,
                ts_headline('english', c.chunk_text, {tsqueryExpr},
                    'MaxWords=50, MinWords=20, StartSel=<mark>, StopSel=</mark>') AS Snippet,
                NULL::int AS PageNumber,
                false AS HasRedaction,
                NULL::text AS PrecedingContext,
                NULL::text AS FollowingContext,
                ts_rank(to_tsvector('english', c.chunk_text), {tsqueryExpr})::float8 AS RelevanceScore,
                d.document_title AS DocumentTitle,
                d.document_date AS DocumentDate,
                d.document_type AS DocumentType,
                d.file_path AS FilePath
            FROM document_chunks c
            JOIN documents d ON d.document_id = c.document_id
            {filterClause}
            ORDER BY RelevanceScore DESC
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
        await using var connection = new NpgsqlConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        var sql = @"
            SELECT
                c.chunk_id::text AS ChunkId,
                c.document_id AS DocumentId,
                d.efta_number AS EftaNumber,
                c.chunk_index AS ChunkIndex,
                c.chunk_text AS ChunkText,
                c.chunk_text AS Snippet,
                NULL::int AS PageNumber,
                false AS HasRedaction,
                NULL::text AS PrecedingContext,
                NULL::text AS FollowingContext,
                1.0::float8 AS RelevanceScore,
                d.document_title AS DocumentTitle,
                d.document_date AS DocumentDate,
                d.document_type AS DocumentType,
                d.file_path AS FilePath
            FROM document_chunks c
            JOIN documents d ON d.document_id = c.document_id
            WHERE c.document_id = @DocumentId
            ORDER BY c.chunk_index";

        var results = await connection.QueryAsync<ChunkSearchResult>(sql, new { DocumentId = documentId });
        return results.ToList();
    }

    private static void AddDateAndTypeFilters(
        ChunkSearchRequest request,
        List<string> conditions,
        DynamicParameters parameters)
    {
        if (!string.IsNullOrEmpty(request.DateFrom))
        {
            conditions.Add("d.document_date >= @DateFrom");
            parameters.Add("DateFrom", request.DateFrom);
        }
        if (!string.IsNullOrEmpty(request.DateTo))
        {
            conditions.Add("d.document_date <= @DateTo");
            parameters.Add("DateTo", request.DateTo);
        }
        if (request.DocumentTypes?.Any() == true)
        {
            conditions.Add("d.document_type = ANY(@DocumentTypes)");
            parameters.Add("DocumentTypes", request.DocumentTypes.ToArray());
        }
    }

    [GeneratedRegex(@"[""'\(\)\*\:\;\!\?\+\-\^~\{\}\[\]\\\/]")]
    private static partial Regex FtsSpecialCharsRegex();

    [GeneratedRegex(@"\s+")]
    private static partial Regex MultipleSpacesRegex();
}
