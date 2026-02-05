using AutoMapper;
using EpsteinDashboard.Application.DTOs;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Microsoft.AspNetCore.Mvc;

namespace EpsteinDashboard.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class DocumentsController : ControllerBase
{
    private readonly IDocumentRepository _repository;
    private readonly IMapper _mapper;

    public DocumentsController(IDocumentRepository repository, IMapper mapper)
    {
        _repository = repository;
        _mapper = mapper;
    }

    [HttpGet]
    public async Task<ActionResult<PagedResult<DocumentListDto>>> GetDocuments(
        [FromQuery] int page = 0,
        [FromQuery] int pageSize = 50,
        [FromQuery] string? documentType = null,
        [FromQuery] string? dateFrom = null,
        [FromQuery] string? dateTo = null,
        [FromQuery] string? sortBy = null,
        [FromQuery] string? sortDirection = "asc",
        CancellationToken cancellationToken = default)
    {
        var result = await _repository.GetFilteredAsync(page, pageSize, documentType, dateFrom, dateTo, sortBy, sortDirection, cancellationToken);
        return Ok(new PagedResult<DocumentListDto>
        {
            Items = _mapper.Map<IReadOnlyList<DocumentListDto>>(result.Items),
            TotalCount = result.TotalCount,
            Page = result.Page,
            PageSize = result.PageSize
        });
    }

    [HttpGet("{id:long}")]
    public async Task<ActionResult<DocumentDto>> GetDocument(long id, CancellationToken cancellationToken)
    {
        var document = await _repository.GetByIdAsync(id, cancellationToken);
        if (document == null) return NotFound();
        return Ok(_mapper.Map<DocumentDto>(document));
    }

    [HttpGet("{id:long}/entities")]
    public async Task<ActionResult<DocumentDto>> GetDocumentEntities(long id, CancellationToken cancellationToken)
    {
        var document = await _repository.GetWithEntitiesAsync(id, cancellationToken);
        if (document == null) return NotFound();
        return Ok(_mapper.Map<DocumentDto>(document));
    }

    [HttpGet("types")]
    public async Task<ActionResult<IReadOnlyList<string>>> GetDocumentTypes(CancellationToken cancellationToken)
    {
        var types = await _repository.GetDocumentTypesAsync(cancellationToken);
        return Ok(types);
    }

    [HttpGet("efta/{eftaNumber}")]
    public async Task<ActionResult<DocumentDto>> GetByEftaNumber(string eftaNumber, CancellationToken cancellationToken)
    {
        var document = await _repository.GetByEftaNumberAsync(eftaNumber, cancellationToken);
        if (document == null) return NotFound();
        return Ok(_mapper.Map<DocumentDto>(document));
    }
}
