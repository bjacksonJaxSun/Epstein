using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EpsteinDashboard.Infrastructure.Data.Configurations;

public class ExtractionLogConfiguration : IEntityTypeConfiguration<ExtractionLog>
{
    public void Configure(EntityTypeBuilder<ExtractionLog> builder)
    {
        builder.ToTable("extraction_log");
        builder.HasKey(e => e.LogId);

        builder.Property(e => e.LogId).HasColumnName("log_id");
        builder.Property(e => e.DocumentId).HasColumnName("document_id");
        builder.Property(e => e.MediaFileId).HasColumnName("media_file_id");
        builder.Property(e => e.ExtractionType).HasColumnName("extraction_type");
        builder.Property(e => e.Status).HasColumnName("status");
        builder.Property(e => e.EntitiesExtracted).HasColumnName("entities_extracted");
        builder.Property(e => e.RelationshipsExtracted).HasColumnName("relationships_extracted");
        builder.Property(e => e.EventsExtracted).HasColumnName("events_extracted");
        builder.Property(e => e.ErrorMessage).HasColumnName("error_message");
        builder.Property(e => e.Warnings).HasColumnName("warnings");
        builder.Property(e => e.ProcessingTimeMs).HasColumnName("processing_time_ms");
        builder.Property(e => e.CreatedAt).HasColumnName("created_at");

        builder.HasOne(e => e.Document)
            .WithMany(d => d.ExtractionLogs)
            .HasForeignKey(e => e.DocumentId)
            .OnDelete(DeleteBehavior.SetNull);

        builder.HasOne(e => e.MediaFile)
            .WithMany(m => m.ExtractionLogs)
            .HasForeignKey(e => e.MediaFileId)
            .OnDelete(DeleteBehavior.SetNull);
    }
}
