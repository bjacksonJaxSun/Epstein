using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EpsteinDashboard.Infrastructure.Data.Configurations;

public class LocationConfiguration : IEntityTypeConfiguration<Location>
{
    public void Configure(EntityTypeBuilder<Location> builder)
    {
        builder.ToTable("locations");
        builder.HasKey(e => e.LocationId);

        builder.Property(e => e.LocationId).HasColumnName("location_id");
        builder.Property(e => e.LocationName).HasColumnName("location_name").IsRequired();
        builder.Property(e => e.LocationType).HasColumnName("location_type");
        builder.Property(e => e.StreetAddress).HasColumnName("street_address");
        builder.Property(e => e.City).HasColumnName("city");
        builder.Property(e => e.StateProvince).HasColumnName("state_province");
        builder.Property(e => e.Country).HasColumnName("country");
        builder.Property(e => e.PostalCode).HasColumnName("postal_code");
        builder.Property(e => e.Latitude).HasColumnName("latitude");
        builder.Property(e => e.Longitude).HasColumnName("longitude");
        builder.Property(e => e.OwnerPersonId).HasColumnName("owner_person_id");
        builder.Property(e => e.OwnerOrganizationId).HasColumnName("owner_organization_id");
        builder.Property(e => e.Description).HasColumnName("description");
        builder.Property(e => e.FirstMentionedInDocId).HasColumnName("first_mentioned_in_doc_id");
        builder.Property(e => e.CreatedAt).HasColumnName("created_at").HasColumnType("timestamptz");
        builder.Property(e => e.UpdatedAt).HasColumnName("updated_at").HasColumnType("timestamptz");

        builder.HasOne(e => e.OwnerPerson)
            .WithMany(p => p.OwnedLocations)
            .HasForeignKey(e => e.OwnerPersonId)
            .OnDelete(DeleteBehavior.SetNull);

        builder.HasOne(e => e.OwnerOrganization)
            .WithMany(o => o.OwnedLocations)
            .HasForeignKey(e => e.OwnerOrganizationId)
            .OnDelete(DeleteBehavior.SetNull);

        builder.HasOne(e => e.FirstMentionedInDocument)
            .WithMany(d => d.MentionedLocations)
            .HasForeignKey(e => e.FirstMentionedInDocId)
            .OnDelete(DeleteBehavior.SetNull);
    }
}
