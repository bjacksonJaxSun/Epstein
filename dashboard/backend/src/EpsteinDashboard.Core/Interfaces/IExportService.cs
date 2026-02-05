namespace EpsteinDashboard.Core.Interfaces;

public interface IExportService
{
    Task<byte[]> ExportToCsvAsync(string entityType, Dictionary<string, string>? filters = null, CancellationToken cancellationToken = default);
    Task<byte[]> ExportToJsonAsync(string entityType, Dictionary<string, string>? filters = null, CancellationToken cancellationToken = default);
}
