using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EpsteinDashboard.Infrastructure.Data.Configurations;

public class EvidenceItemConfiguration : IEntityTypeConfiguration<EvidenceItem>
{
    public void Configure(EntityTypeBuilder<EvidenceItem> builder)
    {
        builder.ToTable("evidence_items");
        builder.HasKey(e => e.EvidenceId);

        builder.Property(e => e.EvidenceId).HasColumnName("evidence_id");
        builder.Property(e => e.EvidenceType).HasColumnName("evidence_type");
        builder.Property(e => e.Description).HasColumnName("description");
        builder.Property(e => e.EvidenceNumber).HasColumnName("evidence_number");
        builder.Property(e => e.ChainOfCustody).HasColumnName("chain_of_custody");
        builder.Property(e => e.SeizedFromLocationId).HasColumnName("seized_from_location_id");
        builder.Property(e => e.SeizedFromPersonId).HasColumnName("seized_from_person_id");
        builder.Property(e => e.SeizureDate).HasColumnName("seizure_date");
        builder.Property(e => e.CurrentLocation).HasColumnName("current_location");
        builder.Property(e => e.Status).HasColumnName("status");
        builder.Property(e => e.SourceDocumentId).HasColumnName("source_document_id");
        builder.Property(e => e.CreatedAt).HasColumnName("created_at");
        builder.Property(e => e.UpdatedAt).HasColumnName("updated_at");

        builder.HasOne(e => e.SeizedFromLocation)
            .WithMany(l => l.SeizedEvidenceItems)
            .HasForeignKey(e => e.SeizedFromLocationId)
            .OnDelete(DeleteBehavior.SetNull);

        builder.HasOne(e => e.SeizedFromPerson)
            .WithMany(p => p.SeizedFromItems)
            .HasForeignKey(e => e.SeizedFromPersonId)
            .OnDelete(DeleteBehavior.SetNull);

        builder.HasOne(e => e.SourceDocument)
            .WithMany(d => d.SourceEvidenceItems)
            .HasForeignKey(e => e.SourceDocumentId)
            .OnDelete(DeleteBehavior.SetNull);
    }
}
