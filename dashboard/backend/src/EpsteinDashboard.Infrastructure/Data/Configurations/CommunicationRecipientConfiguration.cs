using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EpsteinDashboard.Infrastructure.Data.Configurations;

public class CommunicationRecipientConfiguration : IEntityTypeConfiguration<CommunicationRecipient>
{
    public void Configure(EntityTypeBuilder<CommunicationRecipient> builder)
    {
        builder.ToTable("communication_recipients");
        builder.HasKey(e => e.CommunicationRecipientId);

        builder.Property(e => e.CommunicationRecipientId).HasColumnName("communication_recipient_id");
        builder.Property(e => e.CommunicationId).HasColumnName("communication_id");
        builder.Property(e => e.PersonId).HasColumnName("person_id");
        builder.Property(e => e.OrganizationId).HasColumnName("organization_id");
        builder.Property(e => e.RecipientType).HasColumnName("recipient_type");
        builder.Property(e => e.CreatedAt).HasColumnName("created_at");

        builder.HasOne(e => e.Communication)
            .WithMany(c => c.Recipients)
            .HasForeignKey(e => e.CommunicationId)
            .OnDelete(DeleteBehavior.Cascade);

        builder.HasOne(e => e.Person)
            .WithMany(p => p.ReceivedCommunications)
            .HasForeignKey(e => e.PersonId)
            .OnDelete(DeleteBehavior.SetNull);

        builder.HasOne(e => e.Organization)
            .WithMany(o => o.ReceivedCommunications)
            .HasForeignKey(e => e.OrganizationId)
            .OnDelete(DeleteBehavior.SetNull);
    }
}
