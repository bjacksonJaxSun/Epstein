using EpsteinDashboard.Core.Entities;
using EpsteinDashboard.Core.Models;

namespace EpsteinDashboard.Core.Interfaces;

public interface IMediaRepository : IRepository<MediaFile>
{
    Task<MediaFile?> GetWithAnalysisAsync(long id, CancellationToken cancellationToken = default);
    Task<PagedResult<MediaFile>> GetFilteredAsync(int page, int pageSize, string? mediaType = null, string? sortBy = null, string? sortDirection = null, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<ImageAnalysis>> GetAnalysesForMediaAsync(long mediaFileId, CancellationToken cancellationToken = default);
    Task<MediaPositionResult?> GetMediaPositionAsync(long id, int pageSize, string? mediaType = null, CancellationToken cancellationToken = default);
}
