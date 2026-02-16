using System.Text;
using System.Text.Json.Serialization;
using System.Threading.RateLimiting;
using EpsteinDashboard.Api;
using EpsteinDashboard.Api.Hubs;
using EpsteinDashboard.Application;
using EpsteinDashboard.Application.Authorization;
using EpsteinDashboard.Infrastructure;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.RateLimiting;
using Microsoft.IdentityModel.Tokens;

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

// Configure JWT Authentication
var jwtSecret = builder.Configuration["Jwt:Secret"]
    ?? throw new InvalidOperationException("JWT secret not configured. Add Jwt:Secret to appsettings.json");

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidateAudience = true,
            ValidateLifetime = true,
            ValidateIssuerSigningKey = true,
            ValidIssuer = builder.Configuration["Jwt:Issuer"],
            ValidAudience = builder.Configuration["Jwt:Audience"],
            IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtSecret)),
            ClockSkew = TimeSpan.Zero
        };
    });

// Configure Authorization policies for tier-based access
builder.Services.AddAuthorizationBuilder()
    .AddPolicy("FreemiumTier", policy => policy.Requirements.Add(new TierRequirement(0)))
    .AddPolicy("BasicTier", policy => policy.Requirements.Add(new TierRequirement(1)))
    .AddPolicy("PremiumTier", policy => policy.Requirements.Add(new TierRequirement(2)))
    .AddPolicy("AdminTier", policy => policy.Requirements.Add(new TierRequirement(3)));

builder.Services.AddSingleton<IAuthorizationHandler, TierRequirementHandler>();

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

// Rate limiting - protects against abuse while supporting high concurrency
// Works in both VM and Container Apps environments
builder.Services.AddRateLimiter(options =>
{
    options.GlobalLimiter = PartitionedRateLimiter.Create<HttpContext, string>(context =>
        RateLimitPartition.GetFixedWindowLimiter(
            partitionKey: context.Connection.RemoteIpAddress?.ToString() ?? "unknown",
            factory: _ => new FixedWindowRateLimiterOptions
            {
                PermitLimit = 100,
                Window = TimeSpan.FromMinutes(1),
                QueueProcessingOrder = QueueProcessingOrder.OldestFirst,
                QueueLimit = 10
            }));

    options.OnRejected = async (context, token) =>
    {
        context.HttpContext.Response.StatusCode = StatusCodes.Status429TooManyRequests;
        await context.HttpContext.Response.WriteAsync("Too many requests. Please try again later.", token);
    };
});

// Health checks for container orchestration (works with both VM and Container Apps)
builder.Services.AddHealthChecks();

var app = builder.Build();

// Seed admin user on startup
await DatabaseSeeder.SeedAdminUserAsync(app.Services);

// Swagger - enabled in all environments for now (can be restricted later)
// To disable in production: check app.Environment.IsProduction()
app.UseSwagger();
app.UseSwaggerUI(c =>
{
    c.SwaggerEndpoint("/swagger/v1/swagger.json", "Epstein Dashboard API v1");
    c.RoutePrefix = "swagger";
});

app.UseCors("Frontend");
app.UseRateLimiter();

// Serve static files from wwwroot
app.UseDefaultFiles();
app.UseStaticFiles();

app.UseAuthentication();
app.UseAuthorization();

app.MapControllers();
app.MapHub<ExtractionHub>("/hubs/extraction");

// Health endpoints for container orchestration (liveness/readiness probes)
// These work with both the current VM setup and future Container Apps
app.MapGet("/health", () => Results.Ok(new { status = "healthy", timestamp = DateTime.UtcNow }));
app.MapGet("/ready", () => Results.Ok(new { status = "ready", timestamp = DateTime.UtcNow }));
app.MapHealthChecks("/healthz");

// SPA fallback - serve index.html for any unmatched routes (for client-side routing)
app.MapFallbackToFile("index.html");

app.Run();
