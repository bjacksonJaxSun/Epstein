namespace EpsteinDashboard.Core.Entities;

public class FinancialTransaction
{
    public long TransactionId { get; set; }
    public string? TransactionType { get; set; }
    public decimal? Amount { get; set; }
    public string? Currency { get; set; }
    public long? FromPersonId { get; set; }
    public long? FromOrganizationId { get; set; }
    public long? ToPersonId { get; set; }
    public long? ToOrganizationId { get; set; }
    public string? TransactionDate { get; set; }
    public string? Purpose { get; set; }
    public string? ReferenceNumber { get; set; }
    public string? FromAccount { get; set; }
    public string? ToAccount { get; set; }
    public string? BankName { get; set; }
    public long? SourceDocumentId { get; set; }
    public string? CreatedAt { get; set; }
    public string? UpdatedAt { get; set; }

    // Navigation properties
    public Person? FromPerson { get; set; }
    public Organization? FromOrganization { get; set; }
    public Person? ToPerson { get; set; }
    public Organization? ToOrganization { get; set; }
    public Document? SourceDocument { get; set; }
}
