using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace EpsteinDashboard.Infrastructure.Data.Configurations;

public class FaceClusterConfiguration : IEntityTypeConfiguration<FaceCluster>
{
    public void Configure(EntityTypeBuilder<FaceCluster> builder)
    {
        builder.ToTable("face_clusters");
        builder.HasKey(x => x.ClusterId);

        builder.Property(x => x.ClusterId).HasColumnName("cluster_id");
        builder.Property(x => x.PersonId).HasColumnName("person_id");
        builder.Property(x => x.PersonName).HasColumnName("person_name");
        builder.Property(x => x.FaceCount).HasColumnName("face_count");
        builder.Property(x => x.RepresentativeFaceId).HasColumnName("representative_face_id");
        builder.Property(x => x.CentroidEncoding).HasColumnName("centroid_encoding");
        builder.Property(x => x.CreatedAt).HasColumnName("created_at");
        builder.Property(x => x.UpdatedAt).HasColumnName("updated_at");

        builder.HasOne(x => x.Person)
            .WithMany()
            .HasForeignKey(x => x.PersonId);
    }
}
