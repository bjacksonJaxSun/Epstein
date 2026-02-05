namespace EpsteinDashboard.Core.Models;

public class ConnectionPath
{
    public bool Found { get; set; }
    public List<ConnectionPathNode> Path { get; set; } = new();
    public List<ConnectionPathRelationship> Relationships { get; set; } = new();
    public int TotalHops { get; set; }
}

public class ConnectionPathNode
{
    public long PersonId { get; set; }
    public string FullName { get; set; } = string.Empty;
    public string? PrimaryRole { get; set; }
}

public class ConnectionPathRelationship
{
    public long FromPersonId { get; set; }
    public long ToPersonId { get; set; }
    public string? RelationshipType { get; set; }
    public string? ConfidenceLevel { get; set; }
}
