using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EpsteinDashboard.Infrastructure.Data.Configurations;

public class FinancialTransactionConfiguration : IEntityTypeConfiguration<FinancialTransaction>
{
    public void Configure(EntityTypeBuilder<FinancialTransaction> builder)
    {
        builder.ToTable("financial_transactions");
        builder.HasKey(e => e.TransactionId);

        builder.Property(e => e.TransactionId).HasColumnName("transaction_id");
        builder.Property(e => e.TransactionType).HasColumnName("transaction_type");
        builder.Property(e => e.Amount).HasColumnName("amount");
        builder.Property(e => e.Currency).HasColumnName("currency");
        builder.Property(e => e.FromPersonId).HasColumnName("from_person_id");
        builder.Property(e => e.FromOrganizationId).HasColumnName("from_organization_id");
        builder.Property(e => e.ToPersonId).HasColumnName("to_person_id");
        builder.Property(e => e.ToOrganizationId).HasColumnName("to_organization_id");
        builder.Property(e => e.TransactionDate).HasColumnName("transaction_date");
        builder.Property(e => e.Purpose).HasColumnName("purpose");
        builder.Property(e => e.ReferenceNumber).HasColumnName("reference_number");
        builder.Property(e => e.FromAccount).HasColumnName("from_account");
        builder.Property(e => e.ToAccount).HasColumnName("to_account");
        builder.Property(e => e.BankName).HasColumnName("bank_name");
        builder.Property(e => e.SourceDocumentId).HasColumnName("source_document_id");
        builder.Property(e => e.CreatedAt).HasColumnName("created_at").HasColumnType("timestamptz");
        builder.Property(e => e.UpdatedAt).HasColumnName("updated_at").HasColumnType("timestamptz");

        builder.HasOne(e => e.FromPerson)
            .WithMany(p => p.TransactionsAsFrom)
            .HasForeignKey(e => e.FromPersonId)
            .OnDelete(DeleteBehavior.SetNull);

        builder.HasOne(e => e.FromOrganization)
            .WithMany(o => o.TransactionsAsFrom)
            .HasForeignKey(e => e.FromOrganizationId)
            .OnDelete(DeleteBehavior.SetNull);

        builder.HasOne(e => e.ToPerson)
            .WithMany(p => p.TransactionsAsTo)
            .HasForeignKey(e => e.ToPersonId)
            .OnDelete(DeleteBehavior.SetNull);

        builder.HasOne(e => e.ToOrganization)
            .WithMany(o => o.TransactionsAsTo)
            .HasForeignKey(e => e.ToOrganizationId)
            .OnDelete(DeleteBehavior.SetNull);

        builder.HasOne(e => e.SourceDocument)
            .WithMany(d => d.SourceTransactions)
            .HasForeignKey(e => e.SourceDocumentId)
            .OnDelete(DeleteBehavior.SetNull);
    }
}
