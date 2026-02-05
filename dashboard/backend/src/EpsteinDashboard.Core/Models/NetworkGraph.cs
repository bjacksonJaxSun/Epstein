using EpsteinDashboard.Core.Enums;

namespace EpsteinDashboard.Core.Models;

public class NetworkNode
{
    public string Id { get; set; } = string.Empty;
    public string Label { get; set; } = string.Empty;
    public NodeType NodeType { get; set; }
    public Dictionary<string, object?> Properties { get; set; } = new();
}

public class NetworkEdge
{
    public string Source { get; set; } = string.Empty;
    public string Target { get; set; } = string.Empty;
    public string? RelationshipType { get; set; }
    public string? ConfidenceLevel { get; set; }
    public double Weight { get; set; } = 1.0;
}

public class NetworkGraph
{
    public List<NetworkNode> Nodes { get; set; } = new();
    public List<NetworkEdge> Edges { get; set; } = new();
    public string? CenterNodeId { get; set; }
}
