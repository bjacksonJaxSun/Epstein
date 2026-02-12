namespace EpsteinDashboard.Core.Entities;

public class FaceCluster
{
    public long ClusterId { get; set; }
    public long? PersonId { get; set; }
    public string? PersonName { get; set; }
    public int FaceCount { get; set; }
    public long? RepresentativeFaceId { get; set; }
    public byte[]? CentroidEncoding { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime UpdatedAt { get; set; }

    public Person? Person { get; set; }
    public FaceDetection? RepresentativeFace { get; set; }
    public ICollection<FaceDetection> Faces { get; set; } = new List<FaceDetection>();
}
