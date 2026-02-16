using EpsteinDashboard.Application.Services;
using EpsteinDashboard.Core.Interfaces;
using Microsoft.Extensions.DependencyInjection;

namespace EpsteinDashboard.Application;

public static class DependencyInjection
{
    public static IServiceCollection AddApplicationServices(this IServiceCollection services)
    {
        services.AddAutoMapper(typeof(DependencyInjection).Assembly);

        services.AddScoped<TimelineService>();
        services.AddScoped<NetworkAnalysisService>();
        services.AddScoped<FinancialAnalysisService>();
        services.AddScoped<IExportService, ExportService>();

        // Authentication services
        services.AddScoped<IAuthService, AuthService>();

        return services;
    }
}
