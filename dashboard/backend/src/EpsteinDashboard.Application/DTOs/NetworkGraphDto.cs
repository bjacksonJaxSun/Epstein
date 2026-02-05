using EpsteinDashboard.Core.Enums;

namespace EpsteinDashboard.Application.DTOs;

public class NetworkGraphDto
{
    public List<NetworkNodeDto> Nodes { get; set; } = new();
    public List<NetworkEdgeDto> Edges { get; set; } = new();
    public string? CenterNodeId { get; set; }
}

public class NetworkNodeDto
{
    public string Id { get; set; } = string.Empty;
    public string Label { get; set; } = string.Empty;
    public string NodeType { get; set; } = string.Empty;
    public Dictionary<string, object?> Properties { get; set; } = new();
}

public class NetworkEdgeDto
{
    public string Source { get; set; } = string.Empty;
    public string Target { get; set; } = string.Empty;
    public string? RelationshipType { get; set; }
    public string? ConfidenceLevel { get; set; }
    public double Weight { get; set; }
}
