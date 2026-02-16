using EpsteinDashboard.Core.Entities;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;

namespace EpsteinDashboard.Api;

public static class DatabaseSeeder
{
    public static async Task SeedAdminUserAsync(IServiceProvider services)
    {
        using var scope = services.CreateScope();
        var context = scope.ServiceProvider.GetRequiredService<EpsteinDbContext>();
        var authService = scope.ServiceProvider.GetRequiredService<IAuthService>();

        // Ensure auth tables exist
        await EnsureAuthTablesExistAsync(context);

        // Ensure roles are seeded
        await SeedRolesAsync(context);

        // Check if admin exists
        var adminExists = await context.Users.AnyAsync(u => u.Username == "admin");
        if (adminExists) return;

        // Get admin role
        var adminRole = await context.Roles.FirstOrDefaultAsync(r => r.Name == "admin");
        if (adminRole == null)
        {
            Console.WriteLine("Admin role not found. Database seeding may have failed.");
            return;
        }

        // Get admin password from environment variable or use default
        var adminPassword = Environment.GetEnvironmentVariable("ADMIN_INITIAL_PASSWORD") ?? "ChangeMe123!";

        // Create admin user
        var admin = new User
        {
            Username = "admin",
            Email = "admin@epsteindashboard.local",
            PasswordHash = authService.HashPassword(adminPassword),
            IsActive = true,
            IsEmailVerified = true,
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };

        context.Users.Add(admin);
        await context.SaveChangesAsync();

        // Assign admin role
        context.UserRoles.Add(new UserRole
        {
            UserId = admin.UserId,
            RoleId = adminRole.RoleId,
            AssignedAt = DateTime.UtcNow
        });

        await context.SaveChangesAsync();

        Console.WriteLine($"Admin user created successfully. Username: admin, Password: {adminPassword}");
    }

    private static async Task EnsureAuthTablesExistAsync(EpsteinDbContext context)
    {
        var sql = @"
            -- Users table
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGSERIAL PRIMARY KEY,
                username VARCHAR(100) NOT NULL,
                email VARCHAR(255) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                is_email_verified BOOLEAN NOT NULL DEFAULT FALSE,
                last_login_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username);
            CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email);

            -- Roles table
            CREATE TABLE IF NOT EXISTS roles (
                role_id BIGSERIAL PRIMARY KEY,
                name VARCHAR(50) NOT NULL,
                description VARCHAR(500),
                tier_level INTEGER NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS ix_roles_name ON roles (name);

            -- User-Role junction table
            CREATE TABLE IF NOT EXISTS user_roles (
                user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                role_id BIGINT NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
                assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (user_id, role_id)
            );

            -- Refresh tokens table
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                token_id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                token_hash VARCHAR(255) NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                revoked_at TIMESTAMPTZ,
                replaced_by_token_id BIGINT REFERENCES refresh_tokens(token_id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id ON refresh_tokens (user_id);
            CREATE INDEX IF NOT EXISTS ix_refresh_tokens_token_hash ON refresh_tokens (token_hash);
        ";

        try
        {
            await context.Database.ExecuteSqlRawAsync(sql);
            Console.WriteLine("Auth tables verified/created successfully.");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Warning: Could not create auth tables: {ex.Message}");
        }
    }

    private static async Task SeedRolesAsync(EpsteinDbContext context)
    {
        var existingRoles = await context.Roles.ToListAsync();

        var rolesToSeed = new[]
        {
            new Role { RoleId = 1, Name = "freemium", Description = "Access to sample/limited data only", TierLevel = 0 },
            new Role { RoleId = 2, Name = "basic", Description = "Access to images, people, documents, etc.", TierLevel = 1 },
            new Role { RoleId = 3, Name = "premium", Description = "Access to AI chat and deeper analysis features", TierLevel = 2 },
            new Role { RoleId = 4, Name = "admin", Description = "System administrator with full access", TierLevel = 3 }
        };

        foreach (var role in rolesToSeed)
        {
            if (!existingRoles.Any(r => r.Name == role.Name))
            {
                // Use raw SQL to insert with specific ID
                await context.Database.ExecuteSqlRawAsync(
                    "INSERT INTO roles (role_id, name, description, tier_level) VALUES ({0}, {1}, {2}, {3}) ON CONFLICT (role_id) DO NOTHING",
                    role.RoleId, role.Name, role.Description, role.TierLevel);
            }
        }

        // Reset sequence
        await context.Database.ExecuteSqlRawAsync(
            "SELECT setval('roles_role_id_seq', (SELECT COALESCE(MAX(role_id), 1) FROM roles))");

        Console.WriteLine("Roles seeded successfully.");
    }
}
