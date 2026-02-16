using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EpsteinDashboard.Infrastructure.Data.Configurations;

public class RoleConfiguration : IEntityTypeConfiguration<Role>
{
    public void Configure(EntityTypeBuilder<Role> builder)
    {
        builder.ToTable("roles");
        builder.HasKey(e => e.RoleId);

        builder.Property(e => e.RoleId).HasColumnName("role_id");
        builder.Property(e => e.Name).HasColumnName("name").HasMaxLength(50).IsRequired();
        builder.Property(e => e.Description).HasColumnName("description").HasMaxLength(500);
        builder.Property(e => e.TierLevel).HasColumnName("tier_level").IsRequired();

        builder.HasIndex(e => e.Name).IsUnique();

        // Seed default roles
        builder.HasData(
            new Role { RoleId = 1, Name = "freemium", Description = "Access to sample/limited data only", TierLevel = 0 },
            new Role { RoleId = 2, Name = "basic", Description = "Access to images, people, documents, etc.", TierLevel = 1 },
            new Role { RoleId = 3, Name = "premium", Description = "Access to AI chat and deeper analysis features", TierLevel = 2 },
            new Role { RoleId = 4, Name = "admin", Description = "System administrator with full access", TierLevel = 3 }
        );
    }
}
