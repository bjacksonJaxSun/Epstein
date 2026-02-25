using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EpsteinDashboard.Infrastructure.Data.Configurations;

public class OrganizationConfiguration : IEntityTypeConfiguration<Organization>
{
    public void Configure(EntityTypeBuilder<Organization> builder)
    {
        builder.ToTable("organizations");
        builder.HasKey(e => e.OrganizationId);

        builder.Property(e => e.OrganizationId).HasColumnName("organization_id");
        builder.Property(e => e.OrganizationName).HasColumnName("organization_name").IsRequired();
        builder.Property(e => e.OrganizationType).HasColumnName("organization_type");
        builder.Property(e => e.ParentOrganizationId).HasColumnName("parent_organization_id");
        builder.Property(e => e.HeadquartersLocation).HasColumnName("headquarters_location");
        builder.Property(e => e.Website).HasColumnName("website");
        builder.Property(e => e.Description).HasColumnName("description");
        builder.Property(e => e.FirstMentionedInDocId).HasColumnName("first_mentioned_in_doc_id");
        builder.Property(e => e.CreatedAt).HasColumnName("created_at").HasColumnType("timestamptz");
        builder.Property(e => e.UpdatedAt).HasColumnName("updated_at").HasColumnType("timestamptz");

        builder.HasOne(e => e.ParentOrganization)
            .WithMany(e => e.ChildOrganizations)
            .HasForeignKey(e => e.ParentOrganizationId)
            .OnDelete(DeleteBehavior.SetNull);

        builder.HasOne(e => e.FirstMentionedInDocument)
            .WithMany(d => d.MentionedOrganizations)
            .HasForeignKey(e => e.FirstMentionedInDocId)
            .OnDelete(DeleteBehavior.SetNull);
    }
}
