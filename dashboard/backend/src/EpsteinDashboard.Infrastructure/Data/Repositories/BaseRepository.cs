using System.Linq.Expressions;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Microsoft.EntityFrameworkCore;

namespace EpsteinDashboard.Infrastructure.Data.Repositories;

public abstract class BaseRepository<T> : IRepository<T> where T : class
{
    protected readonly EpsteinDbContext Context;
    protected readonly DbSet<T> DbSet;

    protected BaseRepository(EpsteinDbContext context)
    {
        Context = context;
        DbSet = context.Set<T>();
    }

    public virtual async Task<T?> GetByIdAsync(long id, CancellationToken cancellationToken = default)
    {
        return await DbSet.FindAsync(new object[] { id }, cancellationToken);
    }

    public virtual async Task<PagedResult<T>> GetPagedAsync(int page, int pageSize, string? sortBy = null, string? sortDirection = null, CancellationToken cancellationToken = default)
    {
        var query = DbSet.AsNoTracking();
        var totalCount = await query.CountAsync(cancellationToken);

        if (!string.IsNullOrEmpty(sortBy))
        {
            query = ApplySort(query, sortBy, sortDirection);
        }

        var items = await query
            .Skip(page * pageSize)
            .Take(pageSize)
            .ToListAsync(cancellationToken);

        return new PagedResult<T>
        {
            Items = items,
            TotalCount = totalCount,
            Page = page,
            PageSize = pageSize
        };
    }

    public virtual async Task<IReadOnlyList<T>> GetAllAsync(CancellationToken cancellationToken = default)
    {
        return await DbSet.AsNoTracking().ToListAsync(cancellationToken);
    }

    public virtual async Task<int> CountAsync(CancellationToken cancellationToken = default)
    {
        return await DbSet.CountAsync(cancellationToken);
    }

    protected IQueryable<T> ApplySort(IQueryable<T> query, string sortBy, string? sortDirection)
    {
        var entityType = typeof(T);
        var property = entityType.GetProperties()
            .FirstOrDefault(p => string.Equals(p.Name, sortBy, StringComparison.OrdinalIgnoreCase));

        if (property == null) return query;

        var parameter = Expression.Parameter(entityType, "x");
        var propertyAccess = Expression.MakeMemberAccess(parameter, property);
        var orderByExp = Expression.Lambda(propertyAccess, parameter);

        var methodName = string.Equals(sortDirection, "desc", StringComparison.OrdinalIgnoreCase)
            ? "OrderByDescending"
            : "OrderBy";

        var resultExpression = Expression.Call(
            typeof(Queryable),
            methodName,
            new[] { entityType, property.PropertyType },
            query.Expression,
            Expression.Quote(orderByExp));

        return query.Provider.CreateQuery<T>(resultExpression);
    }
}
