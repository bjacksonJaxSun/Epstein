namespace EpsteinDashboard.Core.Entities;

public class DocumentClassification
{
    public long ClassificationId { get; set; }
    public long MediaFileId { get; set; }
    public bool IsDocument { get; set; }
    public bool IsPhoto { get; set; }
    public string? DocumentType { get; set; }
    public string? DocumentSubtype { get; set; }
    public bool HasHandwriting { get; set; }
    public bool HasSignature { get; set; }
    public bool HasLetterhead { get; set; }
    public bool HasStamp { get; set; }
    public double? TextDensity { get; set; }
    public string? EstimatedDate { get; set; }
    public double? Confidence { get; set; }
    public string? ClassificationMethod { get; set; }
    public DateTime CreatedAt { get; set; }

    public MediaFile? MediaFile { get; set; }
}
