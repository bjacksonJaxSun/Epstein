using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EpsteinDashboard.Infrastructure.Data.Configurations;

public class CommunicationConfiguration : IEntityTypeConfiguration<Communication>
{
    public void Configure(EntityTypeBuilder<Communication> builder)
    {
        builder.ToTable("communications");
        builder.HasKey(e => e.CommunicationId);

        builder.Property(e => e.CommunicationId).HasColumnName("communication_id");
        builder.Property(e => e.CommunicationType).HasColumnName("communication_type");
        builder.Property(e => e.SenderPersonId).HasColumnName("sender_person_id");
        builder.Property(e => e.SenderOrganizationId).HasColumnName("sender_organization_id");
        builder.Property(e => e.Subject).HasColumnName("subject");
        builder.Property(e => e.BodyText).HasColumnName("body_text");
        builder.Property(e => e.CommunicationDate).HasColumnName("communication_date");
        builder.Property(e => e.CommunicationTime).HasColumnName("communication_time");
        builder.Property(e => e.SourceDocumentId).HasColumnName("source_document_id");
        builder.Property(e => e.HasAttachments).HasColumnName("has_attachments");
        builder.Property(e => e.AttachmentCount).HasColumnName("attachment_count");
        builder.Property(e => e.CreatedAt).HasColumnName("created_at");
        builder.Property(e => e.UpdatedAt).HasColumnName("updated_at");

        builder.HasOne(e => e.SenderPerson)
            .WithMany(p => p.SentCommunications)
            .HasForeignKey(e => e.SenderPersonId)
            .OnDelete(DeleteBehavior.SetNull);

        builder.HasOne(e => e.SenderOrganization)
            .WithMany(o => o.SentCommunications)
            .HasForeignKey(e => e.SenderOrganizationId)
            .OnDelete(DeleteBehavior.SetNull);

        builder.HasOne(e => e.SourceDocument)
            .WithMany(d => d.SourceCommunications)
            .HasForeignKey(e => e.SourceDocumentId)
            .OnDelete(DeleteBehavior.SetNull);
    }
}
