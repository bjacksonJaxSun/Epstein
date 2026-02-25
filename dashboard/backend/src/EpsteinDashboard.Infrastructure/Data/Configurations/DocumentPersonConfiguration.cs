using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EpsteinDashboard.Infrastructure.Data.Configurations;

public class DocumentPersonConfiguration : IEntityTypeConfiguration<DocumentPerson>
{
    public void Configure(EntityTypeBuilder<DocumentPerson> builder)
    {
        builder.ToTable("document_people");
        builder.HasKey(e => e.Id);

        builder.Property(e => e.Id).HasColumnName("id");
        builder.Property(e => e.DocumentId).HasColumnName("document_id");
        builder.Property(e => e.PersonId).HasColumnName("person_id");
        builder.Property(e => e.MentionCount).HasColumnName("mention_count");
        builder.Property(e => e.MentionContext).HasColumnName("mention_context");
        builder.Property(e => e.RoleInDocument).HasColumnName("role_in_document");
        builder.Property(e => e.Confidence).HasColumnName("confidence");
        builder.Property(e => e.CreatedAt).HasColumnName("created_at").HasColumnType("timestamptz");

        builder.HasIndex(e => new { e.DocumentId, e.PersonId }).IsUnique();

        builder.HasOne(e => e.Document)
            .WithMany(d => d.DocumentPeople)
            .HasForeignKey(e => e.DocumentId)
            .OnDelete(DeleteBehavior.Cascade);

        builder.HasOne(e => e.Person)
            .WithMany(p => p.DocumentMentions)
            .HasForeignKey(e => e.PersonId)
            .OnDelete(DeleteBehavior.Cascade);
    }
}
