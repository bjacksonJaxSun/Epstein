using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Infrastructure.Data;
using EpsteinDashboard.Infrastructure.Data.Repositories;
using EpsteinDashboard.Infrastructure.Search;
using EpsteinDashboard.Infrastructure.Services;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace EpsteinDashboard.Infrastructure;

public static class DependencyInjection
{
    public static IServiceCollection AddInfrastructure(this IServiceCollection services, IConfiguration configuration)
    {
        var connectionString = configuration.GetConnectionString("EpsteinDb")
            ?? throw new InvalidOperationException("EpsteinDb connection string not configured.");

        services.AddDbContext<EpsteinDbContext>(options =>
        {
            options.UseNpgsql(connectionString, npgsqlOptions =>
            {
                npgsqlOptions.CommandTimeout(60);
            });
            options.UseQueryTrackingBehavior(QueryTrackingBehavior.NoTracking);
        });

        // Repositories
        services.AddScoped<IDocumentRepository, DocumentRepository>();
        services.AddScoped<IPersonRepository, PersonRepository>();
        services.AddScoped<IOrganizationRepository, OrganizationRepository>();
        services.AddScoped<ILocationRepository, LocationRepository>();
        services.AddScoped<IEventRepository, EventRepository>();
        services.AddScoped<IRelationshipRepository, RelationshipRepository>();
        services.AddScoped<ICommunicationRepository, CommunicationRepository>();
        services.AddScoped<IFinancialTransactionRepository, FinancialTransactionRepository>();
        services.AddScoped<IMediaRepository, MediaRepository>();
        services.AddScoped<IEvidenceRepository, EvidenceRepository>();

        // Authentication repositories
        services.AddScoped<IUserRepository, UserRepository>();
        services.AddScoped<IRefreshTokenRepository, RefreshTokenRepository>();

        // File resolution services
        services.AddSingleton<IMediaFileService, MediaFileService>();

        // Search and graph services
        services.AddScoped<ISearchService, Fts5SearchProvider>();
        services.AddScoped<IChunkSearchService, ChunkSearchProvider>();
        services.AddScoped<IGraphQueryService, GraphQueryService>();

        return services;
    }
}
