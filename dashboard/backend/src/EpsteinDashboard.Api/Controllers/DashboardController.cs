using EpsteinDashboard.Application.DTOs;
using EpsteinDashboard.Infrastructure.Data;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace EpsteinDashboard.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class DashboardController : ControllerBase
{
    private readonly EpsteinDbContext _context;

    public DashboardController(EpsteinDbContext context)
    {
        _context = context;
    }

    [HttpGet("stats")]
    public async Task<ActionResult<DashboardStatsDto>> GetStats(CancellationToken cancellationToken)
    {
        var stats = new DashboardStatsDto
        {
            TotalDocuments = await _context.Documents.CountAsync(cancellationToken),
            TotalPeople = await _context.People.CountAsync(cancellationToken),
            TotalOrganizations = await _context.Organizations.CountAsync(cancellationToken),
            TotalLocations = await _context.Locations.CountAsync(cancellationToken),
            TotalEvents = await _context.Events.CountAsync(cancellationToken),
            TotalRelationships = await _context.Relationships.CountAsync(cancellationToken),
            TotalCommunications = await _context.Communications.CountAsync(cancellationToken),
            TotalFinancialTransactions = await _context.FinancialTransactions.CountAsync(cancellationToken),
            TotalMediaFiles = await _context.MediaFiles.CountAsync(cancellationToken),
            TotalEvidenceItems = await _context.EvidenceItems.CountAsync(cancellationToken),
            TotalExtractionLogs = await _context.ExtractionLogs.CountAsync(cancellationToken)
        };

        return Ok(stats);
    }
}
