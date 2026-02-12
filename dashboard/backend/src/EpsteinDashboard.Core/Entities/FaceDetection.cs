namespace EpsteinDashboard.Core.Entities;

public class FaceDetection
{
    public long FaceId { get; set; }
    public long MediaFileId { get; set; }
    public int FaceIndex { get; set; }
    public string? BoundingBox { get; set; }
    public byte[]? FaceEncoding { get; set; }
    public long? ClusterId { get; set; }
    public double? Confidence { get; set; }
    public DateTime CreatedAt { get; set; }

    public MediaFile? MediaFile { get; set; }
    public FaceCluster? Cluster { get; set; }
}
