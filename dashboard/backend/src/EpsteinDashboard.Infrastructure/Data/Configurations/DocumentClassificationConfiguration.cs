using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EpsteinDashboard.Infrastructure.Data.Configurations;

public class DocumentClassificationConfiguration : IEntityTypeConfiguration<DocumentClassification>
{
    public void Configure(EntityTypeBuilder<DocumentClassification> builder)
    {
        builder.ToTable("document_classifications");
        builder.HasKey(x => x.ClassificationId);

        builder.Property(x => x.ClassificationId).HasColumnName("classification_id");
        builder.Property(x => x.MediaFileId).HasColumnName("media_file_id");
        builder.Property(x => x.IsDocument).HasColumnName("is_document");
        builder.Property(x => x.IsPhoto).HasColumnName("is_photo");
        builder.Property(x => x.DocumentType).HasColumnName("document_type");
        builder.Property(x => x.DocumentSubtype).HasColumnName("document_subtype");
        builder.Property(x => x.HasHandwriting).HasColumnName("has_handwriting");
        builder.Property(x => x.HasSignature).HasColumnName("has_signature");
        builder.Property(x => x.HasLetterhead).HasColumnName("has_letterhead");
        builder.Property(x => x.HasStamp).HasColumnName("has_stamp");
        builder.Property(x => x.TextDensity).HasColumnName("text_density");
        builder.Property(x => x.EstimatedDate).HasColumnName("estimated_date");
        builder.Property(x => x.Confidence).HasColumnName("confidence");
        builder.Property(x => x.ClassificationMethod).HasColumnName("classification_method");
        builder.Property(x => x.CreatedAt).HasColumnName("created_at");

        builder.HasOne(x => x.MediaFile)
            .WithMany()
            .HasForeignKey(x => x.MediaFileId);
    }
}
