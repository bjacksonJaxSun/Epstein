using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EpsteinDashboard.Infrastructure.Data.Configurations;

public class MediaFileConfiguration : IEntityTypeConfiguration<MediaFile>
{
    public void Configure(EntityTypeBuilder<MediaFile> builder)
    {
        builder.ToTable("media_files");
        builder.HasKey(e => e.MediaFileId);

        builder.Property(e => e.MediaFileId).HasColumnName("media_file_id");
        builder.Property(e => e.FilePath).HasColumnName("file_path");
        builder.Property(e => e.FileName).HasColumnName("file_name");
        builder.Property(e => e.MediaType).HasColumnName("media_type");
        builder.Property(e => e.FileFormat).HasColumnName("file_format");
        builder.Property(e => e.FileSizeBytes).HasColumnName("file_size_bytes");
        builder.Property(e => e.Checksum).HasColumnName("checksum").HasMaxLength(64);
        builder.Property(e => e.DateTaken).HasColumnName("date_taken");
        builder.Property(e => e.CameraMake).HasColumnName("camera_make");
        builder.Property(e => e.CameraModel).HasColumnName("camera_model");
        builder.Property(e => e.GpsLatitude).HasColumnName("gps_latitude");
        builder.Property(e => e.GpsLongitude).HasColumnName("gps_longitude");
        builder.Property(e => e.GpsAltitude).HasColumnName("gps_altitude");
        builder.Property(e => e.WidthPixels).HasColumnName("width_pixels");
        builder.Property(e => e.HeightPixels).HasColumnName("height_pixels");
        builder.Property(e => e.DurationSeconds).HasColumnName("duration_seconds");
        builder.Property(e => e.Orientation).HasColumnName("orientation");
        builder.Property(e => e.OriginalFilename).HasColumnName("original_filename");
        builder.Property(e => e.Caption).HasColumnName("caption");
        builder.Property(e => e.SourceDocumentId).HasColumnName("source_document_id");
        builder.Property(e => e.EvidenceItemId).HasColumnName("evidence_item_id");
        builder.Property(e => e.LocationId).HasColumnName("location_id");
        builder.Property(e => e.IsExplicit).HasColumnName("is_explicit");
        builder.Property(e => e.IsSensitive).HasColumnName("is_sensitive");
        builder.Property(e => e.ClassificationLevel).HasColumnName("classification_level");
        builder.Property(e => e.IsLikelyPhoto).HasColumnName("is_likely_photo");
        builder.Property(e => e.CreatedAt).HasColumnName("created_at").HasColumnType("timestamptz");
        builder.Property(e => e.UpdatedAt).HasColumnName("updated_at").HasColumnType("timestamptz");

        builder.HasOne(e => e.SourceDocument)
            .WithMany(d => d.SourceMediaFiles)
            .HasForeignKey(e => e.SourceDocumentId)
            .OnDelete(DeleteBehavior.SetNull);

        builder.HasOne(e => e.EvidenceItem)
            .WithMany(ei => ei.MediaFiles)
            .HasForeignKey(e => e.EvidenceItemId)
            .OnDelete(DeleteBehavior.SetNull);

        builder.HasOne(e => e.Location)
            .WithMany(l => l.MediaFiles)
            .HasForeignKey(e => e.LocationId)
            .OnDelete(DeleteBehavior.SetNull);
    }
}
