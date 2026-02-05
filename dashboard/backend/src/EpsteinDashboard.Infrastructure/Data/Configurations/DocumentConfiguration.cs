using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EpsteinDashboard.Infrastructure.Data.Configurations;

public class DocumentConfiguration : IEntityTypeConfiguration<Document>
{
    public void Configure(EntityTypeBuilder<Document> builder)
    {
        builder.ToTable("documents");
        builder.HasKey(e => e.DocumentId);

        builder.Property(e => e.DocumentId).HasColumnName("document_id");
        builder.Property(e => e.EftaNumber).HasColumnName("efta_number");
        builder.Property(e => e.FilePath).HasColumnName("file_path");
        builder.Property(e => e.DocumentType).HasColumnName("document_type");
        builder.Property(e => e.DocumentDate).HasColumnName("document_date");
        builder.Property(e => e.DocumentTitle).HasColumnName("document_title");
        builder.Property(e => e.Author).HasColumnName("author");
        builder.Property(e => e.Recipient).HasColumnName("recipient");
        builder.Property(e => e.Subject).HasColumnName("subject");
        builder.Property(e => e.FullText).HasColumnName("full_text");
        builder.Property(e => e.FullTextSearchable).HasColumnName("full_text_searchable");
        builder.Property(e => e.PageCount).HasColumnName("page_count");
        builder.Property(e => e.FileSizeBytes).HasColumnName("file_size_bytes");
        builder.Property(e => e.ClassificationLevel).HasColumnName("classification_level");
        builder.Property(e => e.IsRedacted).HasColumnName("is_redacted");
        builder.Property(e => e.RedactionLevel).HasColumnName("redaction_level");
        builder.Property(e => e.SourceAgency).HasColumnName("source_agency");
        builder.Property(e => e.ExtractionStatus).HasColumnName("extraction_status");
        builder.Property(e => e.ExtractionConfidence).HasColumnName("extraction_confidence");
        builder.Property(e => e.CreatedAt).HasColumnName("created_at");
        builder.Property(e => e.UpdatedAt).HasColumnName("updated_at");

        builder.HasIndex(e => e.EftaNumber).IsUnique();
    }
}
