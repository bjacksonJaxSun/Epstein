using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EpsteinDashboard.Infrastructure.Data.Configurations;

public class ImageAnalysisConfiguration : IEntityTypeConfiguration<ImageAnalysis>
{
    public void Configure(EntityTypeBuilder<ImageAnalysis> builder)
    {
        builder.ToTable("image_analyses");
        builder.HasKey(e => e.AnalysisId);

        builder.Property(e => e.AnalysisId).HasColumnName("analysis_id");
        builder.Property(e => e.MediaFileId).HasColumnName("media_file_id");
        builder.Property(e => e.Description).HasColumnName("description");
        builder.Property(e => e.GeneratedCaption).HasColumnName("generated_caption");
        builder.Property(e => e.Tags).HasColumnName("tags");
        builder.Property(e => e.Categories).HasColumnName("categories");
        builder.Property(e => e.AnalysisProvider).HasColumnName("analysis_provider");
        builder.Property(e => e.AnalysisModelVersion).HasColumnName("analysis_model_version");
        builder.Property(e => e.AnalysisDate).HasColumnName("analysis_date");
        builder.Property(e => e.ConfidenceScore).HasColumnName("confidence_score");
        builder.Property(e => e.ContainsText).HasColumnName("contains_text");
        builder.Property(e => e.ExtractedText).HasColumnName("extracted_text");
        builder.Property(e => e.TextLanguage).HasColumnName("text_language");
        builder.Property(e => e.ContainsFaces).HasColumnName("contains_faces");
        builder.Property(e => e.FaceCount).HasColumnName("face_count");
        builder.Property(e => e.SceneType).HasColumnName("scene_type");
        builder.Property(e => e.IsExplicit).HasColumnName("is_explicit");
        builder.Property(e => e.IsSensitive).HasColumnName("is_sensitive");
        builder.Property(e => e.ModerationLabels).HasColumnName("moderation_labels");
        builder.Property(e => e.DominantColors).HasColumnName("dominant_colors");
        builder.Property(e => e.CreatedAt).HasColumnName("created_at").HasColumnType("timestamptz");
        builder.Property(e => e.UpdatedAt).HasColumnName("updated_at").HasColumnType("timestamptz");

        builder.HasOne(e => e.MediaFile)
            .WithMany(m => m.Analyses)
            .HasForeignKey(e => e.MediaFileId)
            .OnDelete(DeleteBehavior.Cascade);
    }
}
