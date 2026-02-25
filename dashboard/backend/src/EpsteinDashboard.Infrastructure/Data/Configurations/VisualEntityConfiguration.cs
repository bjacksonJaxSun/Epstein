using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EpsteinDashboard.Infrastructure.Data.Configurations;

public class VisualEntityConfiguration : IEntityTypeConfiguration<VisualEntity>
{
    public void Configure(EntityTypeBuilder<VisualEntity> builder)
    {
        builder.ToTable("visual_entities");
        builder.HasKey(e => e.EntityId);

        builder.Property(e => e.EntityId).HasColumnName("entity_id");
        builder.Property(e => e.MediaFileId).HasColumnName("media_file_id");
        builder.Property(e => e.EntityType).HasColumnName("entity_type");
        builder.Property(e => e.EntityLabel).HasColumnName("entity_label");
        builder.Property(e => e.EntityDescription).HasColumnName("entity_description");
        builder.Property(e => e.BboxX).HasColumnName("bbox_x");
        builder.Property(e => e.BboxY).HasColumnName("bbox_y");
        builder.Property(e => e.BboxWidth).HasColumnName("bbox_width");
        builder.Property(e => e.BboxHeight).HasColumnName("bbox_height");
        builder.Property(e => e.Confidence).HasColumnName("confidence");
        builder.Property(e => e.PersonId).HasColumnName("person_id");
        builder.Property(e => e.EstimatedAgeRange).HasColumnName("estimated_age_range");
        builder.Property(e => e.Gender).HasColumnName("gender");
        builder.Property(e => e.FacialExpression).HasColumnName("facial_expression");
        builder.Property(e => e.FaceEncoding).HasColumnName("face_encoding");
        builder.Property(e => e.Attributes).HasColumnName("attributes");
        builder.Property(e => e.CreatedAt).HasColumnName("created_at").HasColumnType("timestamptz");

        builder.HasOne(e => e.MediaFile)
            .WithMany(m => m.VisualEntities)
            .HasForeignKey(e => e.MediaFileId)
            .OnDelete(DeleteBehavior.Cascade);

        builder.HasOne(e => e.Person)
            .WithMany(p => p.VisualIdentifications)
            .HasForeignKey(e => e.PersonId)
            .OnDelete(DeleteBehavior.SetNull);
    }
}
