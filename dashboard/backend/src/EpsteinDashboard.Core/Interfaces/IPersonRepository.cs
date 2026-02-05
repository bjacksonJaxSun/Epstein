using EpsteinDashboard.Core.Entities;
using EpsteinDashboard.Core.Models;

namespace EpsteinDashboard.Core.Interfaces;

public interface IPersonRepository : IRepository<Person>
{
    Task<Person?> GetByIdWithRelationshipsAsync(long id, CancellationToken cancellationToken = default);
    Task<NetworkGraph> GetNetworkAsync(long personId, int depth = 2, CancellationToken cancellationToken = default);
    Task<PagedResult<Person>> SearchByNameAsync(string name, int page = 0, int pageSize = 50, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<Event>> GetEventsForPersonAsync(long personId, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<Document>> GetDocumentsForPersonAsync(long personId, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<FinancialTransaction>> GetFinancialsForPersonAsync(long personId, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<MediaFile>> GetMediaForPersonAsync(long personId, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<(Person Person, int DocumentCount, int EventCount, int RelationshipCount, int FinancialCount, decimal FinancialTotal, int MediaCount)>> GetAllWithFrequenciesAsync(int limit = 500, CancellationToken cancellationToken = default);
}
