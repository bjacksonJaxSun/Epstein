using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EpsteinDashboard.Infrastructure.Data.Configurations;

public class MediaPersonConfiguration : IEntityTypeConfiguration<MediaPerson>
{
    public void Configure(EntityTypeBuilder<MediaPerson> builder)
    {
        builder.ToTable("media_people");
        builder.HasKey(e => e.MediaPersonId);

        builder.Property(e => e.MediaPersonId).HasColumnName("media_person_id");
        builder.Property(e => e.MediaFileId).HasColumnName("media_file_id");
        builder.Property(e => e.PersonId).HasColumnName("person_id");
        builder.Property(e => e.VisualEntityId).HasColumnName("visual_entity_id");
        builder.Property(e => e.IdentificationMethod).HasColumnName("identification_method");
        builder.Property(e => e.Confidence).HasColumnName("confidence");
        builder.Property(e => e.PositionDescription).HasColumnName("position_description");
        builder.Property(e => e.Notes).HasColumnName("notes");
        builder.Property(e => e.TaggedBy).HasColumnName("tagged_by");
        builder.Property(e => e.Verified).HasColumnName("verified");
        builder.Property(e => e.VerifiedBy).HasColumnName("verified_by");
        builder.Property(e => e.VerifiedDate).HasColumnName("verified_date");
        builder.Property(e => e.CreatedAt).HasColumnName("created_at").HasColumnType("timestamptz");
        builder.Property(e => e.UpdatedAt).HasColumnName("updated_at").HasColumnType("timestamptz");

        builder.HasIndex(e => new { e.MediaFileId, e.PersonId }).IsUnique();

        builder.HasOne(e => e.MediaFile)
            .WithMany(m => m.TaggedPersons)
            .HasForeignKey(e => e.MediaFileId)
            .OnDelete(DeleteBehavior.Cascade);

        builder.HasOne(e => e.Person)
            .WithMany(p => p.MediaAppearances)
            .HasForeignKey(e => e.PersonId)
            .OnDelete(DeleteBehavior.Cascade);

        builder.HasOne(e => e.VisualEntity)
            .WithMany(v => v.MediaPersonLinks)
            .HasForeignKey(e => e.VisualEntityId)
            .OnDelete(DeleteBehavior.SetNull);
    }
}
