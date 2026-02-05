using AutoMapper;
using EpsteinDashboard.Application.DTOs;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Microsoft.AspNetCore.Mvc;

namespace EpsteinDashboard.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class OrganizationsController : ControllerBase
{
    private readonly IOrganizationRepository _repository;
    private readonly IMapper _mapper;

    public OrganizationsController(IOrganizationRepository repository, IMapper mapper)
    {
        _repository = repository;
        _mapper = mapper;
    }

    [HttpGet]
    public async Task<ActionResult<PagedResult<OrganizationDto>>> GetOrganizations(
        [FromQuery] int page = 0,
        [FromQuery] int pageSize = 50,
        [FromQuery] string? sortBy = null,
        [FromQuery] string? sortDirection = "asc",
        CancellationToken cancellationToken = default)
    {
        var result = await _repository.GetPagedAsync(page, pageSize, sortBy, sortDirection, cancellationToken);
        return Ok(new PagedResult<OrganizationDto>
        {
            Items = _mapper.Map<IReadOnlyList<OrganizationDto>>(result.Items),
            TotalCount = result.TotalCount,
            Page = result.Page,
            PageSize = result.PageSize
        });
    }

    [HttpGet("{id:long}")]
    public async Task<ActionResult<OrganizationDto>> GetOrganization(long id, CancellationToken cancellationToken)
    {
        var org = await _repository.GetWithChildrenAsync(id, cancellationToken);
        if (org == null) return NotFound();
        return Ok(_mapper.Map<OrganizationDto>(org));
    }

    [HttpGet("{id:long}/documents")]
    public async Task<ActionResult<IReadOnlyList<DocumentListDto>>> GetDocuments(long id, CancellationToken cancellationToken)
    {
        var documents = await _repository.GetDocumentsAsync(id, cancellationToken);
        return Ok(_mapper.Map<IReadOnlyList<DocumentListDto>>(documents));
    }

    [HttpGet("{id:long}/financials")]
    public async Task<ActionResult<IReadOnlyList<FinancialTransactionDto>>> GetFinancials(long id, CancellationToken cancellationToken)
    {
        var transactions = await _repository.GetFinancialTransactionsAsync(id, cancellationToken);
        return Ok(_mapper.Map<IReadOnlyList<FinancialTransactionDto>>(transactions));
    }

    [HttpGet("{id:long}/people")]
    public async Task<ActionResult<IReadOnlyList<PersonListDto>>> GetPeople(long id, CancellationToken cancellationToken)
    {
        var people = await _repository.GetRelatedPeopleAsync(id, cancellationToken);
        return Ok(_mapper.Map<IReadOnlyList<PersonListDto>>(people));
    }
}
