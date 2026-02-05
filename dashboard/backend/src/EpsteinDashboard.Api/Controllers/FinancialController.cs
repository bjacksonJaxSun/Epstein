using AutoMapper;
using EpsteinDashboard.Application.DTOs;
using EpsteinDashboard.Application.Services;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Microsoft.AspNetCore.Mvc;

namespace EpsteinDashboard.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class FinancialController : ControllerBase
{
    private readonly IFinancialTransactionRepository _repository;
    private readonly FinancialAnalysisService _financialService;
    private readonly IMapper _mapper;

    public FinancialController(
        IFinancialTransactionRepository repository,
        FinancialAnalysisService financialService,
        IMapper mapper)
    {
        _repository = repository;
        _financialService = financialService;
        _mapper = mapper;
    }

    [HttpGet("transactions")]
    public async Task<ActionResult<PagedResult<FinancialTransactionDto>>> GetTransactions(
        [FromQuery] int page = 0,
        [FromQuery] int pageSize = 50,
        [FromQuery] string? transactionType = null,
        [FromQuery] string? dateFrom = null,
        [FromQuery] string? dateTo = null,
        [FromQuery] string? sortBy = null,
        [FromQuery] string? sortDirection = "asc",
        CancellationToken cancellationToken = default)
    {
        var result = await _repository.GetFilteredAsync(page, pageSize, transactionType, dateFrom, dateTo, sortBy, sortDirection, cancellationToken);
        return Ok(new PagedResult<FinancialTransactionDto>
        {
            Items = _mapper.Map<IReadOnlyList<FinancialTransactionDto>>(result.Items),
            TotalCount = result.TotalCount,
            Page = result.Page,
            PageSize = result.PageSize
        });
    }

    [HttpGet("flows")]
    public async Task<ActionResult<FinancialFlowDto>> GetFlows(CancellationToken cancellationToken)
    {
        var flows = await _financialService.GetFlowsAsync(cancellationToken);
        return Ok(flows);
    }

    [HttpGet("summary")]
    public async Task<ActionResult<FinancialSummary>> GetSummary(CancellationToken cancellationToken)
    {
        var summary = await _financialService.GetSummaryAsync(cancellationToken);
        return Ok(summary);
    }
}
