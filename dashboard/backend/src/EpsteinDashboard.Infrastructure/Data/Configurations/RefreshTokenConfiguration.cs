using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EpsteinDashboard.Infrastructure.Data.Configurations;

public class RefreshTokenConfiguration : IEntityTypeConfiguration<RefreshToken>
{
    public void Configure(EntityTypeBuilder<RefreshToken> builder)
    {
        builder.ToTable("refresh_tokens");
        builder.HasKey(e => e.TokenId);

        builder.Property(e => e.TokenId).HasColumnName("token_id");
        builder.Property(e => e.UserId).HasColumnName("user_id");
        builder.Property(e => e.TokenHash).HasColumnName("token_hash").HasMaxLength(255).IsRequired();
        builder.Property(e => e.ExpiresAt).HasColumnName("expires_at");
        builder.Property(e => e.CreatedAt).HasColumnName("created_at");
        builder.Property(e => e.RevokedAt).HasColumnName("revoked_at");
        builder.Property(e => e.ReplacedByTokenId).HasColumnName("replaced_by_token_id");

        // Ignore computed properties
        builder.Ignore(e => e.IsExpired);
        builder.Ignore(e => e.IsRevoked);
        builder.Ignore(e => e.IsActive);

        builder.HasIndex(e => e.UserId);
        builder.HasIndex(e => e.TokenHash);

        builder.HasOne(e => e.User)
            .WithMany(u => u.RefreshTokens)
            .HasForeignKey(e => e.UserId)
            .OnDelete(DeleteBehavior.Cascade);

        builder.HasOne(e => e.ReplacedByToken)
            .WithMany()
            .HasForeignKey(e => e.ReplacedByTokenId)
            .OnDelete(DeleteBehavior.SetNull);
    }
}
