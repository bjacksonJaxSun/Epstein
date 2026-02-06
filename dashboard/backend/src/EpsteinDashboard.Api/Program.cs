using System.Text.Json.Serialization;
using EpsteinDashboard.Api.Hubs;
using EpsteinDashboard.Application;
using EpsteinDashboard.Infrastructure;

var builder = WebApplication.CreateBuilder(args);

// Add controllers with JSON options
builder.Services.AddControllers()
    .AddJsonOptions(options =>
    {
        options.JsonSerializerOptions.DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull;
        options.JsonSerializerOptions.PropertyNamingPolicy = System.Text.Json.JsonNamingPolicy.CamelCase;
    });

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen(c =>
{
    c.SwaggerDoc("v1", new Microsoft.OpenApi.Models.OpenApiInfo
    {
        Title = "Epstein Document Analysis Dashboard API",
        Version = "v1",
        Description = "API for querying and analyzing extracted document data from the Epstein case files."
    });
});

builder.Services.AddSignalR();

// Add infrastructure (DbContext, repositories, search)
builder.Services.AddInfrastructure(builder.Configuration);

// Add application services (AutoMapper, services)
builder.Services.AddApplicationServices();

// CORS for React frontend
builder.Services.AddCors(options =>
{
    options.AddPolicy("Frontend", policy =>
    {
        policy.SetIsOriginAllowed(_ => true) // Allow any origin for LAN access during development
            .AllowAnyHeader()
            .AllowAnyMethod()
            .AllowCredentials();
    });
});

var app = builder.Build();

app.UseSwagger();
app.UseSwaggerUI(c =>
{
    c.SwaggerEndpoint("/swagger/v1/swagger.json", "Epstein Dashboard API v1");
    c.RoutePrefix = "swagger";
});

app.UseCors("Frontend");

app.MapControllers();
app.MapHub<ExtractionHub>("/hubs/extraction");
app.MapGet("/health", () => Results.Ok(new { status = "healthy", timestamp = DateTime.UtcNow }));

app.Run();
