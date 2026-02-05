namespace EpsteinDashboard.Core.Entities;

public class ExtractionLog
{
    public long LogId { get; set; }
    public long? DocumentId { get; set; }
    public long? MediaFileId { get; set; }
    public string? ExtractionType { get; set; }
    public string? Status { get; set; }
    public int? EntitiesExtracted { get; set; }
    public int? RelationshipsExtracted { get; set; }
    public int? EventsExtracted { get; set; }
    public string? ErrorMessage { get; set; }
    public string? Warnings { get; set; } // JSON
    public int? ProcessingTimeMs { get; set; }
    public string? CreatedAt { get; set; }

    // Navigation properties
    public Document? Document { get; set; }
    public MediaFile? MediaFile { get; set; }
}
