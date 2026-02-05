using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EpsteinDashboard.Infrastructure.Data.Configurations;

public class PersonConfiguration : IEntityTypeConfiguration<Person>
{
    public void Configure(EntityTypeBuilder<Person> builder)
    {
        builder.ToTable("people");
        builder.HasKey(e => e.PersonId);

        builder.Property(e => e.PersonId).HasColumnName("person_id");
        builder.Property(e => e.FullName).HasColumnName("full_name").IsRequired();
        builder.Property(e => e.NameVariations).HasColumnName("name_variations");
        builder.Property(e => e.PrimaryRole).HasColumnName("primary_role");
        builder.Property(e => e.Roles).HasColumnName("roles");
        builder.Property(e => e.EmailAddresses).HasColumnName("email_addresses");
        builder.Property(e => e.PhoneNumbers).HasColumnName("phone_numbers");
        builder.Property(e => e.Addresses).HasColumnName("addresses");
        builder.Property(e => e.IsRedacted).HasColumnName("is_redacted");
        builder.Property(e => e.VictimIdentifier).HasColumnName("victim_identifier");
        builder.Property(e => e.DateOfBirth).HasColumnName("date_of_birth");
        builder.Property(e => e.Nationality).HasColumnName("nationality");
        builder.Property(e => e.Occupation).HasColumnName("occupation");
        builder.Property(e => e.FirstMentionedInDocId).HasColumnName("first_mentioned_in_doc_id");
        builder.Property(e => e.ConfidenceLevel).HasColumnName("confidence_level");
        builder.Property(e => e.Notes).HasColumnName("notes");
        builder.Property(e => e.CreatedAt).HasColumnName("created_at");
        builder.Property(e => e.UpdatedAt).HasColumnName("updated_at");

        builder.HasOne(e => e.FirstMentionedInDocument)
            .WithMany(d => d.MentionedPersons)
            .HasForeignKey(e => e.FirstMentionedInDocId)
            .OnDelete(DeleteBehavior.SetNull);
    }
}
