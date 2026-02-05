using EpsteinDashboard.Core.Entities;

namespace EpsteinDashboard.Core.Interfaces;

public interface IOrganizationRepository : IRepository<Organization>
{
    Task<Organization?> GetWithChildrenAsync(long id, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<Document>> GetDocumentsAsync(long organizationId, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<FinancialTransaction>> GetFinancialTransactionsAsync(long organizationId, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<Person>> GetRelatedPeopleAsync(long organizationId, CancellationToken cancellationToken = default);
}
