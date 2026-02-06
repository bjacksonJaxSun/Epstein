using Dapper;
using EpsteinDashboard.Core.Entities;
using EpsteinDashboard.Core.Enums;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;

namespace EpsteinDashboard.Infrastructure.Data.Repositories;

public class PersonRepository : BaseRepository<Person>, IPersonRepository
{
    private readonly string _connectionString;

    public PersonRepository(EpsteinDbContext context, IConfiguration configuration) : base(context)
    {
        _connectionString = configuration.GetConnectionString("EpsteinDb")
            ?? throw new InvalidOperationException("EpsteinDb connection string not configured.");
    }

    public async Task<Person?> GetByIdWithRelationshipsAsync(long id, CancellationToken cancellationToken = default)
    {
        return await DbSet.AsNoTracking()
            .Include(p => p.RelationshipsAsPerson1).ThenInclude(r => r.Person2)
            .Include(p => p.RelationshipsAsPerson2).ThenInclude(r => r.Person1)
            .Include(p => p.FirstMentionedInDocument)
            .FirstOrDefaultAsync(p => p.PersonId == id, cancellationToken);
    }

    public async Task<NetworkGraph> GetNetworkAsync(long personId, int depth = 2, CancellationToken cancellationToken = default)
    {
        await using var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        // Use recursive CTE to find connected people up to N depth
        var sql = @"
            WITH RECURSIVE network(person_id, depth) AS (
                SELECT @PersonId, 0
                UNION
                SELECT CASE
                    WHEN r.person1_id = network.person_id THEN r.person2_id
                    ELSE r.person1_id
                END, network.depth + 1
                FROM relationships r
                JOIN network ON (r.person1_id = network.person_id OR r.person2_id = network.person_id)
                WHERE network.depth < @Depth
            )
            SELECT DISTINCT p.person_id, p.full_name, p.primary_role
            FROM network n
            JOIN people p ON p.person_id = n.person_id;";

        var people = (await connection.QueryAsync<dynamic>(sql, new { PersonId = personId, Depth = depth })).ToList();

        var personIds = people.Select(p => (long)p.person_id).ToList();

        var relSql = @"
            SELECT r.relationship_id, r.person1_id, r.person2_id, r.relationship_type, r.confidence_level
            FROM relationships r
            WHERE r.person1_id IN @Ids AND r.person2_id IN @Ids;";

        var relationships = (await connection.QueryAsync<dynamic>(relSql, new { Ids = personIds })).ToList();

        var graph = new NetworkGraph
        {
            CenterNodeId = $"person-{personId}"
        };

        foreach (var p in people)
        {
            graph.Nodes.Add(new NetworkNode
            {
                Id = $"person-{p.person_id}",
                Label = (string)(p.full_name ?? "Unknown"),
                NodeType = NodeType.Person,
                Properties = new Dictionary<string, object?>
                {
                    ["primaryRole"] = p.primary_role
                }
            });
        }

        foreach (var r in relationships)
        {
            graph.Edges.Add(new NetworkEdge
            {
                Source = $"person-{r.person1_id}",
                Target = $"person-{r.person2_id}",
                RelationshipType = r.relationship_type,
                ConfidenceLevel = r.confidence_level,
                Weight = 1.0
            });
        }

        return graph;
    }

    public async Task<PagedResult<Person>> SearchByNameAsync(string name, int page = 0, int pageSize = 50, CancellationToken cancellationToken = default)
    {
        var query = DbSet.AsNoTracking()
            .Where(p => EF.Functions.Like(p.FullName, $"%{name}%"));

        var totalCount = await query.CountAsync(cancellationToken);
        var items = await query
            .OrderBy(p => p.FullName)
            .Skip(page * pageSize)
            .Take(pageSize)
            .ToListAsync(cancellationToken);

        return new PagedResult<Person>
        {
            Items = items,
            TotalCount = totalCount,
            Page = page,
            PageSize = pageSize
        };
    }

    public async Task<IReadOnlyList<Event>> GetEventsForPersonAsync(long personId, CancellationToken cancellationToken = default)
    {
        return await Context.EventParticipants.AsNoTracking()
            .Where(ep => ep.PersonId == personId)
            .Include(ep => ep.Event)
                .ThenInclude(e => e!.Location)
            .Select(ep => ep.Event!)
            .ToListAsync(cancellationToken);
    }

    public async Task<IReadOnlyList<Document>> GetDocumentsForPersonAsync(long personId, CancellationToken cancellationToken = default)
    {
        // Documents where this person is mentioned (via document_people junction table)
        var docs = await Context.DocumentPersons.AsNoTracking()
            .Where(dp => dp.PersonId == personId)
            .Include(dp => dp.Document)
            .Select(dp => dp.Document!)
            .ToListAsync(cancellationToken);

        return docs;
    }

    public async Task<IReadOnlyList<FinancialTransaction>> GetFinancialsForPersonAsync(long personId, CancellationToken cancellationToken = default)
    {
        return await Context.FinancialTransactions.AsNoTracking()
            .Where(t => t.FromPersonId == personId || t.ToPersonId == personId)
            .Include(t => t.FromPerson)
            .Include(t => t.ToPerson)
            .Include(t => t.FromOrganization)
            .Include(t => t.ToOrganization)
            .ToListAsync(cancellationToken);
    }

    public async Task<IReadOnlyList<MediaFile>> GetMediaForPersonAsync(long personId, CancellationToken cancellationToken = default)
    {
        return await Context.MediaPersons.AsNoTracking()
            .Where(mp => mp.PersonId == personId)
            .Include(mp => mp.MediaFile)
            .Select(mp => mp.MediaFile!)
            .ToListAsync(cancellationToken);
    }

    public async Task<IReadOnlyList<(Person Person, int DocumentCount, int EventCount, int RelationshipCount, int FinancialCount, decimal FinancialTotal, int MediaCount)>> GetAllWithFrequenciesAsync(int limit = 500, CancellationToken cancellationToken = default)
    {
        await using var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        var sql = @"
            SELECT
                p.person_id,
                p.full_name,
                p.primary_role,
                p.occupation,
                p.confidence_level,
                COALESCE(doc.cnt, 0) as document_count,
                COALESCE(evt.cnt, 0) as event_count,
                COALESCE(rel.cnt, 0) as relationship_count,
                COALESCE(fin.cnt, 0) as financial_count,
                COALESCE(fin.total, 0) as financial_total,
                COALESCE(med.cnt, 0) as media_count
            FROM people p
            LEFT JOIN (
                SELECT person_id, COUNT(*) as cnt
                FROM document_people
                GROUP BY person_id
            ) doc ON doc.person_id = p.person_id
            LEFT JOIN (
                SELECT person_id, COUNT(*) as cnt
                FROM event_participants
                GROUP BY person_id
            ) evt ON evt.person_id = p.person_id
            LEFT JOIN (
                SELECT person_id, COUNT(*) as cnt
                FROM (
                    SELECT person1_id as person_id FROM relationships
                    UNION ALL
                    SELECT person2_id as person_id FROM relationships
                )
                GROUP BY person_id
            ) rel ON rel.person_id = p.person_id
            LEFT JOIN (
                SELECT person_id, COUNT(*) as cnt, SUM(COALESCE(amount, 0)) as total
                FROM (
                    SELECT from_person_id as person_id, amount FROM financial_transactions WHERE from_person_id IS NOT NULL
                    UNION ALL
                    SELECT to_person_id as person_id, amount FROM financial_transactions WHERE to_person_id IS NOT NULL
                )
                GROUP BY person_id
            ) fin ON fin.person_id = p.person_id
            LEFT JOIN (
                SELECT person_id, COUNT(*) as cnt
                FROM media_people
                GROUP BY person_id
            ) med ON med.person_id = p.person_id
            ORDER BY (COALESCE(doc.cnt, 0) + COALESCE(evt.cnt, 0) + COALESCE(rel.cnt, 0) + COALESCE(fin.cnt, 0) + COALESCE(med.cnt, 0)) DESC
            LIMIT @Limit;";

        var results = await connection.QueryAsync<dynamic>(sql, new { Limit = limit });

        return results.Select(r => (
            Person: new Person
            {
                PersonId = (long)r.person_id,
                FullName = (string)(r.full_name ?? "Unknown"),
                PrimaryRole = r.primary_role as string,
                Occupation = r.occupation as string,
                ConfidenceLevel = r.confidence_level as string
            },
            DocumentCount: (int)(r.document_count ?? 0),
            EventCount: (int)(r.event_count ?? 0),
            RelationshipCount: (int)(r.relationship_count ?? 0),
            FinancialCount: (int)(r.financial_count ?? 0),
            FinancialTotal: (decimal)(r.financial_total ?? 0m),
            MediaCount: (int)(r.media_count ?? 0)
        )).ToList();
    }

    public async Task<PagedResult<(Person Person, int DocumentCount, int EventCount, int RelationshipCount, int FinancialCount, int TotalMentions, string? EpsteinRelationship)>> GetPagedWithCountsAsync(
        int page, int pageSize, string? search = null, string? sortBy = null, string? sortDirection = "asc", CancellationToken cancellationToken = default)
    {
        await using var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        var whereClause = string.IsNullOrEmpty(search) ? "" : "WHERE p.full_name LIKE @Search";
        var searchParam = string.IsNullOrEmpty(search) ? null : $"%{search}%";

        var orderColumn = sortBy?.ToLower() switch
        {
            "documentcount" => "document_count",
            "eventcount" => "event_count",
            "relationshipcount" => "relationship_count",
            "totalmentions" => "total_mentions",
            "fullname" => "p.full_name",
            "epsteinrelationship" => "epstein_relationship",
            _ => "total_mentions"
        };
        var orderDir = sortDirection?.ToLower() == "asc" ? "ASC" : "DESC";

        var countSql = $@"
            SELECT COUNT(*) FROM people p {whereClause};";

        var totalCount = await connection.ExecuteScalarAsync<int>(countSql, new { Search = searchParam });

        // Jeffrey Epstein's person_id is 3
        const int EPSTEIN_PERSON_ID = 3;

        var sql = $@"
            SELECT
                p.person_id,
                p.full_name,
                p.primary_role,
                p.occupation,
                p.nationality,
                p.confidence_level,
                COALESCE(doc.cnt, 0) as document_count,
                COALESCE(evt.cnt, 0) as event_count,
                COALESCE(rel.cnt, 0) as relationship_count,
                COALESCE(fin.cnt, 0) as financial_count,
                (COALESCE(doc.cnt, 0) + COALESCE(evt.cnt, 0) + COALESCE(rel.cnt, 0) + COALESCE(fin.cnt, 0)) as total_mentions,
                CASE
                    WHEN epstein_rel.person_id IS NOT NULL THEN COALESCE(p.primary_role, epstein_rel.relationship_type)
                    ELSE NULL
                END as epstein_relationship
            FROM people p
            LEFT JOIN (
                SELECT person_id, COUNT(*) as cnt
                FROM document_people
                GROUP BY person_id
            ) doc ON doc.person_id = p.person_id
            LEFT JOIN (
                SELECT person_id, COUNT(*) as cnt
                FROM event_participants
                GROUP BY person_id
            ) evt ON evt.person_id = p.person_id
            LEFT JOIN (
                SELECT person_id, COUNT(*) as cnt
                FROM (
                    SELECT person1_id as person_id FROM relationships
                    UNION ALL
                    SELECT person2_id as person_id FROM relationships
                )
                GROUP BY person_id
            ) rel ON rel.person_id = p.person_id
            LEFT JOIN (
                SELECT person_id, COUNT(*) as cnt
                FROM (
                    SELECT from_person_id as person_id FROM financial_transactions WHERE from_person_id IS NOT NULL
                    UNION ALL
                    SELECT to_person_id as person_id FROM financial_transactions WHERE to_person_id IS NOT NULL
                )
                GROUP BY person_id
            ) fin ON fin.person_id = p.person_id
            LEFT JOIN (
                SELECT
                    CASE WHEN person1_id = {EPSTEIN_PERSON_ID} THEN person2_id ELSE person1_id END as person_id,
                    GROUP_CONCAT(DISTINCT relationship_type) as relationship_type
                FROM relationships
                WHERE person1_id = {EPSTEIN_PERSON_ID} OR person2_id = {EPSTEIN_PERSON_ID}
                GROUP BY CASE WHEN person1_id = {EPSTEIN_PERSON_ID} THEN person2_id ELSE person1_id END
            ) epstein_rel ON epstein_rel.person_id = p.person_id
            {whereClause}
            ORDER BY {orderColumn} {orderDir}
            LIMIT @PageSize OFFSET @Offset;";

        var results = await connection.QueryAsync<dynamic>(sql, new { Search = searchParam, PageSize = pageSize, Offset = page * pageSize });

        var items = results.Select(r => (
            Person: new Person
            {
                PersonId = (long)r.person_id,
                FullName = (string)(r.full_name ?? "Unknown"),
                PrimaryRole = r.primary_role as string,
                Occupation = r.occupation as string,
                Nationality = r.nationality as string,
                ConfidenceLevel = r.confidence_level as string
            },
            DocumentCount: (int)(r.document_count ?? 0),
            EventCount: (int)(r.event_count ?? 0),
            RelationshipCount: (int)(r.relationship_count ?? 0),
            FinancialCount: (int)(r.financial_count ?? 0),
            TotalMentions: (int)(r.total_mentions ?? 0),
            EpsteinRelationship: r.epstein_relationship as string
        )).ToList();

        return new PagedResult<(Person, int, int, int, int, int, string?)>
        {
            Items = items,
            TotalCount = totalCount,
            Page = page,
            PageSize = pageSize
        };
    }

    public async Task<IReadOnlyList<(string CanonicalName, List<Person> Variants)>> FindDuplicatesAsync(double similarityThreshold = 0.8, CancellationToken cancellationToken = default)
    {
        await using var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        // Get all people with their counts
        var sql = @"
            SELECT
                p.person_id,
                p.full_name,
                p.primary_role,
                p.occupation,
                p.nationality,
                p.confidence_level,
                COALESCE(doc.cnt, 0) as document_count,
                COALESCE(evt.cnt, 0) as event_count,
                COALESCE(rel.cnt, 0) as relationship_count
            FROM people p
            LEFT JOIN (SELECT person_id, COUNT(*) as cnt FROM document_people GROUP BY person_id) doc ON doc.person_id = p.person_id
            LEFT JOIN (SELECT person_id, COUNT(*) as cnt FROM event_participants GROUP BY person_id) evt ON evt.person_id = p.person_id
            LEFT JOIN (SELECT person_id, COUNT(*) as cnt FROM (SELECT person1_id as person_id FROM relationships UNION ALL SELECT person2_id FROM relationships) GROUP BY person_id) rel ON rel.person_id = p.person_id
            ORDER BY (COALESCE(doc.cnt, 0) + COALESCE(evt.cnt, 0) + COALESCE(rel.cnt, 0)) DESC;";

        var people = (await connection.QueryAsync<dynamic>(sql)).ToList();

        // Group by normalized name patterns
        var duplicateGroups = new Dictionary<string, List<Person>>();

        foreach (var p in people)
        {
            var fullName = (string)(p.full_name ?? "");
            var normalizedName = NormalizeName(fullName);

            if (string.IsNullOrWhiteSpace(normalizedName)) continue;

            // Find matching group
            string? matchingKey = null;
            foreach (var key in duplicateGroups.Keys)
            {
                if (AreSimilarNames(normalizedName, key))
                {
                    matchingKey = key;
                    break;
                }
            }

            var person = new Person
            {
                PersonId = (long)p.person_id,
                FullName = fullName,
                PrimaryRole = p.primary_role as string,
                Occupation = p.occupation as string,
                Nationality = p.nationality as string,
                ConfidenceLevel = p.confidence_level as string
            };

            if (matchingKey != null)
            {
                duplicateGroups[matchingKey].Add(person);
            }
            else
            {
                duplicateGroups[normalizedName] = new List<Person> { person };
            }
        }

        // Return only groups with more than one person
        return duplicateGroups
            .Where(g => g.Value.Count > 1)
            .Select(g => (CanonicalName: g.Value.First().FullName, Variants: g.Value))
            .OrderByDescending(g => g.Variants.Count)
            .Take(100)
            .ToList();
    }

    private static string NormalizeName(string name)
    {
        if (string.IsNullOrWhiteSpace(name)) return "";

        // Remove special characters, extra spaces, convert to lowercase
        var normalized = new string(name.ToLowerInvariant()
            .Where(c => char.IsLetterOrDigit(c) || c == ' ')
            .ToArray());

        // Remove common OCR artifacts
        normalized = normalized
            .Replace("  ", " ")
            .Trim();

        return normalized;
    }

    private static bool AreSimilarNames(string name1, string name2)
    {
        if (string.IsNullOrWhiteSpace(name1) || string.IsNullOrWhiteSpace(name2)) return false;

        // Exact match after normalization
        if (name1 == name2) return true;

        // One is substring of other (handles "G Maxwell" vs "Ghislaine Maxwell")
        if (name1.Contains(name2) || name2.Contains(name1)) return true;

        // Calculate similarity
        var distance = LevenshteinDistance(name1, name2);
        var maxLen = Math.Max(name1.Length, name2.Length);
        var similarity = 1.0 - ((double)distance / maxLen);

        return similarity >= 0.8;
    }

    private static int LevenshteinDistance(string s1, string s2)
    {
        var m = s1.Length;
        var n = s2.Length;
        var d = new int[m + 1, n + 1];

        for (var i = 0; i <= m; i++) d[i, 0] = i;
        for (var j = 0; j <= n; j++) d[0, j] = j;

        for (var j = 1; j <= n; j++)
        {
            for (var i = 1; i <= m; i++)
            {
                var cost = s1[i - 1] == s2[j - 1] ? 0 : 1;
                d[i, j] = Math.Min(Math.Min(d[i - 1, j] + 1, d[i, j - 1] + 1), d[i - 1, j - 1] + cost);
            }
        }

        return d[m, n];
    }

    public async Task MergePersonsAsync(long primaryPersonId, IEnumerable<long> mergePersonIds, CancellationToken cancellationToken = default)
    {
        await using var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        using var transaction = await connection.BeginTransactionAsync(cancellationToken);

        try
        {
            foreach (var mergeId in mergePersonIds)
            {
                if (mergeId == primaryPersonId) continue;

                // Update document_people references
                await connection.ExecuteAsync(
                    "UPDATE document_people SET person_id = @PrimaryId WHERE person_id = @MergeId AND NOT EXISTS (SELECT 1 FROM document_people WHERE person_id = @PrimaryId AND document_id = (SELECT document_id FROM document_people WHERE person_id = @MergeId))",
                    new { PrimaryId = primaryPersonId, MergeId = mergeId }, transaction);

                // Update event_participants references
                await connection.ExecuteAsync(
                    "UPDATE event_participants SET person_id = @PrimaryId WHERE person_id = @MergeId AND NOT EXISTS (SELECT 1 FROM event_participants WHERE person_id = @PrimaryId AND event_id = (SELECT event_id FROM event_participants WHERE person_id = @MergeId))",
                    new { PrimaryId = primaryPersonId, MergeId = mergeId }, transaction);

                // Update relationships - person1_id
                await connection.ExecuteAsync(
                    "UPDATE relationships SET person1_id = @PrimaryId WHERE person1_id = @MergeId",
                    new { PrimaryId = primaryPersonId, MergeId = mergeId }, transaction);

                // Update relationships - person2_id
                await connection.ExecuteAsync(
                    "UPDATE relationships SET person2_id = @PrimaryId WHERE person2_id = @MergeId",
                    new { PrimaryId = primaryPersonId, MergeId = mergeId }, transaction);

                // Update financial_transactions - from_person_id
                await connection.ExecuteAsync(
                    "UPDATE financial_transactions SET from_person_id = @PrimaryId WHERE from_person_id = @MergeId",
                    new { PrimaryId = primaryPersonId, MergeId = mergeId }, transaction);

                // Update financial_transactions - to_person_id
                await connection.ExecuteAsync(
                    "UPDATE financial_transactions SET to_person_id = @PrimaryId WHERE to_person_id = @MergeId",
                    new { PrimaryId = primaryPersonId, MergeId = mergeId }, transaction);

                // Update media_people
                await connection.ExecuteAsync(
                    "UPDATE media_people SET person_id = @PrimaryId WHERE person_id = @MergeId AND NOT EXISTS (SELECT 1 FROM media_people WHERE person_id = @PrimaryId AND media_file_id = (SELECT media_file_id FROM media_people WHERE person_id = @MergeId))",
                    new { PrimaryId = primaryPersonId, MergeId = mergeId }, transaction);

                // Delete remaining duplicates and the merged person
                await connection.ExecuteAsync("DELETE FROM document_people WHERE person_id = @MergeId", new { MergeId = mergeId }, transaction);
                await connection.ExecuteAsync("DELETE FROM event_participants WHERE person_id = @MergeId", new { MergeId = mergeId }, transaction);
                await connection.ExecuteAsync("DELETE FROM media_people WHERE person_id = @MergeId", new { MergeId = mergeId }, transaction);
                await connection.ExecuteAsync("DELETE FROM people WHERE person_id = @MergeId", new { MergeId = mergeId }, transaction);
            }

            await transaction.CommitAsync(cancellationToken);
        }
        catch
        {
            await transaction.RollbackAsync(cancellationToken);
            throw;
        }
    }
}
