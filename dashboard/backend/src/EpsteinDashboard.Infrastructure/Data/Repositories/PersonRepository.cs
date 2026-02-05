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
        // Documents where this person is first mentioned
        var docs = await Context.Documents.AsNoTracking()
            .Where(d => d.MentionedPersons.Any(p => p.PersonId == personId))
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
}
