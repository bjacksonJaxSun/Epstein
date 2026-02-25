using Dapper;
using EpsteinDashboard.Core.Enums;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Npgsql;
using Microsoft.Extensions.Configuration;

namespace EpsteinDashboard.Infrastructure.Search;

public class GraphQueryService : IGraphQueryService
{
    private readonly string _connectionString;

    public GraphQueryService(IConfiguration configuration)
    {
        _connectionString = configuration.GetConnectionString("EpsteinDb")
            ?? throw new InvalidOperationException("EpsteinDb connection string not configured.");
    }

    public async Task<NetworkGraph> GetNetworkGraphAsync(long personId, int depth = 2, CancellationToken cancellationToken = default)
    {
        await using var connection = new NpgsqlConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

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

    public async Task<ConnectionPath> FindConnectionPathAsync(long person1Id, long person2Id, int maxDepth = 6, CancellationToken cancellationToken = default)
    {
        await using var connection = new NpgsqlConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        // BFS using recursive CTE to find shortest path
        var sql = @"
            WITH RECURSIVE path_finder(person_id, path, depth) AS (
                SELECT @Person1Id, CAST(@Person1Id AS TEXT), 0
                UNION ALL
                SELECT
                    CASE
                        WHEN r.person1_id = pf.person_id THEN r.person2_id
                        ELSE r.person1_id
                    END,
                    pf.path || ',' || CAST(
                        CASE
                            WHEN r.person1_id = pf.person_id THEN r.person2_id
                            ELSE r.person1_id
                        END AS TEXT),
                    pf.depth + 1
                FROM relationships r
                JOIN path_finder pf ON (r.person1_id = pf.person_id OR r.person2_id = pf.person_id)
                WHERE pf.depth < @MaxDepth
                    AND POSITION(CAST(
                        CASE
                            WHEN r.person1_id = pf.person_id THEN r.person2_id
                            ELSE r.person1_id
                        END AS TEXT) IN pf.path) = 0
            )
            SELECT path, depth
            FROM path_finder
            WHERE person_id = @Person2Id
            ORDER BY depth
            LIMIT 1;";

        var result = await connection.QuerySingleOrDefaultAsync<dynamic>(sql, new
        {
            Person1Id = person1Id,
            Person2Id = person2Id,
            MaxDepth = maxDepth
        });

        if (result == null)
        {
            return new ConnectionPath { Found = false };
        }

        string pathStr = result.path;
        var personIds = pathStr.Split(',').Select(long.Parse).ToList();

        // Get person details
        var peopleSql = "SELECT person_id, full_name, primary_role FROM people WHERE person_id IN @Ids";
        var people = (await connection.QueryAsync<dynamic>(peopleSql, new { Ids = personIds }))
            .ToDictionary(p => (long)p.person_id);

        var pathNodes = new List<ConnectionPathNode>();
        var pathRelationships = new List<ConnectionPathRelationship>();

        foreach (var id in personIds)
        {
            if (people.TryGetValue(id, out var p))
            {
                pathNodes.Add(new ConnectionPathNode
                {
                    PersonId = id,
                    FullName = p.full_name ?? "Unknown",
                    PrimaryRole = p.primary_role
                });
            }
        }

        // Get relationships along the path
        for (int i = 0; i < personIds.Count - 1; i++)
        {
            var relSql = @"
                SELECT relationship_type, confidence_level
                FROM relationships
                WHERE (person1_id = @P1 AND person2_id = @P2)
                   OR (person1_id = @P2 AND person2_id = @P1)
                LIMIT 1";

            var rel = await connection.QuerySingleOrDefaultAsync<dynamic>(relSql, new
            {
                P1 = personIds[i],
                P2 = personIds[i + 1]
            });

            pathRelationships.Add(new ConnectionPathRelationship
            {
                FromPersonId = personIds[i],
                ToPersonId = personIds[i + 1],
                RelationshipType = rel?.relationship_type,
                ConfidenceLevel = rel?.confidence_level
            });
        }

        return new ConnectionPath
        {
            Found = true,
            Path = pathNodes,
            Relationships = pathRelationships,
            TotalHops = (int)result.depth
        };
    }
}
