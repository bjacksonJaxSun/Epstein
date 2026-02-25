namespace EpsteinDashboard.Core.Entities;

public class Document
{
    public long DocumentId { get; set; }
    public string? EftaNumber { get; set; }
    public string? FilePath { get; set; }
    public string? DocumentType { get; set; }
    public DateTime? DocumentDate { get; set; }
    public string? DocumentTitle { get; set; }
    public string? Author { get; set; }
    public string? Recipient { get; set; }
    public string? Subject { get; set; }
    public string? FullText { get; set; }
    public string? FullTextSearchable { get; set; }
    public int? PageCount { get; set; }
    public long? FileSizeBytes { get; set; }
    public string? ClassificationLevel { get; set; }
    public bool? IsRedacted { get; set; }
    public string? RedactionLevel { get; set; }
    public string? SourceAgency { get; set; }
    public string? ExtractionStatus { get; set; }
    public double? ExtractionConfidence { get; set; }
    public DateTime? CreatedAt { get; set; }
    public DateTime? UpdatedAt { get; set; }
    public string? VideoPath { get; set; }
    public string? VideoTranscript { get; set; }
    public DateTime? PhotosCheckedAt { get; set; }
    public string? R2Key { get; set; }
    public string? OcrStatus { get; set; }

    // Navigation properties
    public ICollection<DocumentPerson> DocumentPeople { get; set; } = new List<DocumentPerson>();
    public ICollection<Person> MentionedPersons { get; set; } = new List<Person>();  // Legacy - via FirstMentionedInDocId
    public ICollection<Organization> MentionedOrganizations { get; set; } = new List<Organization>();
    public ICollection<Location> MentionedLocations { get; set; } = new List<Location>();
    public ICollection<Relationship> SourceRelationships { get; set; } = new List<Relationship>();
    public ICollection<Event> SourceEvents { get; set; } = new List<Event>();
    public ICollection<Communication> SourceCommunications { get; set; } = new List<Communication>();
    public ICollection<FinancialTransaction> SourceTransactions { get; set; } = new List<FinancialTransaction>();
    public ICollection<EvidenceItem> SourceEvidenceItems { get; set; } = new List<EvidenceItem>();
    public ICollection<MediaFile> SourceMediaFiles { get; set; } = new List<MediaFile>();
    public ICollection<ExtractionLog> ExtractionLogs { get; set; } = new List<ExtractionLog>();
}
