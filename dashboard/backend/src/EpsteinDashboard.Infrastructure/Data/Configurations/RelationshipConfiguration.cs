using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EpsteinDashboard.Infrastructure.Data.Configurations;

public class RelationshipConfiguration : IEntityTypeConfiguration<Relationship>
{
    public void Configure(EntityTypeBuilder<Relationship> builder)
    {
        builder.ToTable("relationships");
        builder.HasKey(e => e.RelationshipId);

        builder.Property(e => e.RelationshipId).HasColumnName("relationship_id");
        builder.Property(e => e.Person1Id).HasColumnName("person1_id");
        builder.Property(e => e.Person2Id).HasColumnName("person2_id");
        builder.Property(e => e.RelationshipType).HasColumnName("relationship_type");
        builder.Property(e => e.RelationshipDescription).HasColumnName("relationship_description");
        builder.Property(e => e.StartDate).HasColumnName("start_date");
        builder.Property(e => e.EndDate).HasColumnName("end_date");
        builder.Property(e => e.IsCurrent).HasColumnName("is_current");
        builder.Property(e => e.SourceDocumentId).HasColumnName("source_document_id");
        builder.Property(e => e.ConfidenceLevel).HasColumnName("confidence_level");
        builder.Property(e => e.CreatedAt).HasColumnName("created_at");
        builder.Property(e => e.UpdatedAt).HasColumnName("updated_at");

        builder.HasOne(e => e.Person1)
            .WithMany(p => p.RelationshipsAsPerson1)
            .HasForeignKey(e => e.Person1Id)
            .OnDelete(DeleteBehavior.Cascade);

        builder.HasOne(e => e.Person2)
            .WithMany(p => p.RelationshipsAsPerson2)
            .HasForeignKey(e => e.Person2Id)
            .OnDelete(DeleteBehavior.Cascade);

        builder.HasOne(e => e.SourceDocument)
            .WithMany(d => d.SourceRelationships)
            .HasForeignKey(e => e.SourceDocumentId)
            .OnDelete(DeleteBehavior.SetNull);
    }
}
