using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EpsteinDashboard.Infrastructure.Data.Configurations;

public class FaceDetectionConfiguration : IEntityTypeConfiguration<FaceDetection>
{
    public void Configure(EntityTypeBuilder<FaceDetection> builder)
    {
        builder.ToTable("face_detections");
        builder.HasKey(x => x.FaceId);

        builder.Property(x => x.FaceId).HasColumnName("face_id");
        builder.Property(x => x.MediaFileId).HasColumnName("media_file_id");
        builder.Property(x => x.FaceIndex).HasColumnName("face_index");
        builder.Property(x => x.BoundingBox).HasColumnName("bounding_box");
        builder.Property(x => x.FaceEncoding).HasColumnName("face_encoding");
        builder.Property(x => x.ClusterId).HasColumnName("cluster_id");
        builder.Property(x => x.Confidence).HasColumnName("confidence");
        builder.Property(x => x.CreatedAt).HasColumnName("created_at");

        builder.HasOne(x => x.MediaFile)
            .WithMany()
            .HasForeignKey(x => x.MediaFileId);

        builder.HasOne(x => x.Cluster)
            .WithMany(c => c.Faces)
            .HasForeignKey(x => x.ClusterId);
    }
}
