using EpsteinDashboard.Core.Interfaces;
using Microsoft.AspNetCore.Mvc;

namespace EpsteinDashboard.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class ExportController : ControllerBase
{
    private readonly IExportService _exportService;

    public ExportController(IExportService exportService)
    {
        _exportService = exportService;
    }

    [HttpPost("csv")]
    public async Task<IActionResult> ExportCsv(
        [FromQuery] string entityType,
        [FromBody] Dictionary<string, string>? filters = null,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var bytes = await _exportService.ExportToCsvAsync(entityType, filters, cancellationToken);
            return File(bytes, "text/csv", $"{entityType}_{DateTime.UtcNow:yyyyMMdd}.csv");
        }
        catch (ArgumentException ex)
        {
            return BadRequest(ex.Message);
        }
    }

    [HttpPost("json")]
    public async Task<IActionResult> ExportJson(
        [FromQuery] string entityType,
        [FromBody] Dictionary<string, string>? filters = null,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var bytes = await _exportService.ExportToJsonAsync(entityType, filters, cancellationToken);
            return File(bytes, "application/json", $"{entityType}_{DateTime.UtcNow:yyyyMMdd}.json");
        }
        catch (ArgumentException ex)
        {
            return BadRequest(ex.Message);
        }
    }
}
