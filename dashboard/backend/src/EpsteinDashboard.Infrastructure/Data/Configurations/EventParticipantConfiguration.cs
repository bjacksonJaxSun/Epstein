using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EpsteinDashboard.Infrastructure.Data.Configurations;

public class EventParticipantConfiguration : IEntityTypeConfiguration<EventParticipant>
{
    public void Configure(EntityTypeBuilder<EventParticipant> builder)
    {
        builder.ToTable("event_participants");
        builder.HasKey(e => e.ParticipantId);

        builder.Property(e => e.ParticipantId).HasColumnName("participant_id");
        builder.Property(e => e.EventId).HasColumnName("event_id");
        builder.Property(e => e.PersonId).HasColumnName("person_id");
        builder.Property(e => e.OrganizationId).HasColumnName("organization_id");
        builder.Property(e => e.ParticipationRole).HasColumnName("participation_role");
        builder.Property(e => e.Notes).HasColumnName("notes");
        builder.Property(e => e.CreatedAt).HasColumnName("created_at");

        builder.HasOne(e => e.Event)
            .WithMany(ev => ev.Participants)
            .HasForeignKey(e => e.EventId)
            .OnDelete(DeleteBehavior.Cascade);

        builder.HasOne(e => e.Person)
            .WithMany(p => p.EventParticipations)
            .HasForeignKey(e => e.PersonId)
            .OnDelete(DeleteBehavior.SetNull);

        builder.HasOne(e => e.Organization)
            .WithMany(o => o.EventParticipations)
            .HasForeignKey(e => e.OrganizationId)
            .OnDelete(DeleteBehavior.SetNull);
    }
}
