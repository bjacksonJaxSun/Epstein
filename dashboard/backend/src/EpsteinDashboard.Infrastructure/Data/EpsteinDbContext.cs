using EpsteinDashboard.Core.Entities;
using Microsoft.EntityFrameworkCore;

namespace EpsteinDashboard.Infrastructure.Data;

public class EpsteinDbContext : DbContext
{
    public EpsteinDbContext(DbContextOptions<EpsteinDbContext> options) : base(options)
    {
    }

    public DbSet<Document> Documents => Set<Document>();
    public DbSet<Person> People => Set<Person>();
    public DbSet<Organization> Organizations => Set<Organization>();
    public DbSet<Location> Locations => Set<Location>();
    public DbSet<Relationship> Relationships => Set<Relationship>();
    public DbSet<Event> Events => Set<Event>();
    public DbSet<EventParticipant> EventParticipants => Set<EventParticipant>();
    public DbSet<Communication> Communications => Set<Communication>();
    public DbSet<CommunicationRecipient> CommunicationRecipients => Set<CommunicationRecipient>();
    public DbSet<FinancialTransaction> FinancialTransactions => Set<FinancialTransaction>();
    public DbSet<EvidenceItem> EvidenceItems => Set<EvidenceItem>();
    public DbSet<MediaFile> MediaFiles => Set<MediaFile>();
    public DbSet<MediaPerson> MediaPersons => Set<MediaPerson>();
    public DbSet<MediaEvent> MediaEvents => Set<MediaEvent>();
    public DbSet<DocumentPerson> DocumentPersons => Set<DocumentPerson>();
    public DbSet<VisualEntity> VisualEntities => Set<VisualEntity>();
    public DbSet<ImageAnalysis> ImageAnalyses => Set<ImageAnalysis>();
    public DbSet<ExtractionLog> ExtractionLogs => Set<ExtractionLog>();
    public DbSet<FaceDetection> FaceDetections => Set<FaceDetection>();
    public DbSet<FaceCluster> FaceClusters => Set<FaceCluster>();
    public DbSet<DocumentClassification> DocumentClassifications => Set<DocumentClassification>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);
        modelBuilder.ApplyConfigurationsFromAssembly(typeof(EpsteinDbContext).Assembly);
    }
}
