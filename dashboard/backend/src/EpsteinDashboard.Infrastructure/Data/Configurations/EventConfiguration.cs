using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EpsteinDashboard.Infrastructure.Data.Configurations;

public class EventConfiguration : IEntityTypeConfiguration<Event>
{
    public void Configure(EntityTypeBuilder<Event> builder)
    {
        builder.ToTable("events");
        builder.HasKey(e => e.EventId);

        builder.Property(e => e.EventId).HasColumnName("event_id");
        builder.Property(e => e.EventType).HasColumnName("event_type");
        builder.Property(e => e.Title).HasColumnName("title");
        builder.Property(e => e.Description).HasColumnName("description");
        builder.Property(e => e.EventDate).HasColumnName("event_date");
        builder.Property(e => e.EventTime).HasColumnName("event_time");
        builder.Property(e => e.EndDate).HasColumnName("end_date");
        builder.Property(e => e.EndTime).HasColumnName("end_time");
        builder.Property(e => e.DurationMinutes).HasColumnName("duration_minutes");
        builder.Property(e => e.LocationId).HasColumnName("location_id");
        builder.Property(e => e.SourceDocumentId).HasColumnName("source_document_id");
        builder.Property(e => e.AdditionalSourceDocs).HasColumnName("additional_source_docs");
        builder.Property(e => e.ConfidenceLevel).HasColumnName("confidence_level");
        builder.Property(e => e.VerificationStatus).HasColumnName("verification_status");
        builder.Property(e => e.Notes).HasColumnName("notes");
        builder.Property(e => e.CreatedAt).HasColumnName("created_at");
        builder.Property(e => e.UpdatedAt).HasColumnName("updated_at");

        builder.HasOne(e => e.Location)
            .WithMany(l => l.Events)
            .HasForeignKey(e => e.LocationId)
            .OnDelete(DeleteBehavior.SetNull);

        builder.HasOne(e => e.SourceDocument)
            .WithMany(d => d.SourceEvents)
            .HasForeignKey(e => e.SourceDocumentId)
            .OnDelete(DeleteBehavior.SetNull);
    }
}
