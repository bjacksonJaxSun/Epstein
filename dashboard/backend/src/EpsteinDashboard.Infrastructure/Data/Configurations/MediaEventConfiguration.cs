using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EpsteinDashboard.Infrastructure.Data.Configurations;

public class MediaEventConfiguration : IEntityTypeConfiguration<MediaEvent>
{
    public void Configure(EntityTypeBuilder<MediaEvent> builder)
    {
        builder.ToTable("media_events");
        builder.HasKey(e => e.MediaEventId);

        builder.Property(e => e.MediaEventId).HasColumnName("media_event_id");
        builder.Property(e => e.MediaFileId).HasColumnName("media_file_id");
        builder.Property(e => e.EventId).HasColumnName("event_id");
        builder.Property(e => e.IsPrimaryEvidence).HasColumnName("is_primary_evidence");
        builder.Property(e => e.SequenceNumber).HasColumnName("sequence_number");
        builder.Property(e => e.RelationshipDescription).HasColumnName("relationship_description");
        builder.Property(e => e.CreatedAt).HasColumnName("created_at");
        builder.Property(e => e.UpdatedAt).HasColumnName("updated_at");

        builder.HasIndex(e => new { e.MediaFileId, e.EventId }).IsUnique();

        builder.HasOne(e => e.MediaFile)
            .WithMany(m => m.MediaEvents)
            .HasForeignKey(e => e.MediaFileId)
            .OnDelete(DeleteBehavior.Cascade);

        builder.HasOne(e => e.Event)
            .WithMany(ev => ev.MediaEvents)
            .HasForeignKey(e => e.EventId)
            .OnDelete(DeleteBehavior.Cascade);
    }
}
