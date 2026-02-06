using AutoMapper;
using EpsteinDashboard.Application.DTOs;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Microsoft.AspNetCore.Mvc;

namespace EpsteinDashboard.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class EvidenceController : ControllerBase
{
    private readonly IEvidenceRepository _repository;
    private readonly IMapper _mapper;

    public EvidenceController(IEvidenceRepository repository, IMapper mapper)
    {
        _repository = repository;
        _mapper = mapper;
    }

    [HttpGet]
    public async Task<ActionResult<PagedResult<EvidenceItemDto>>> GetEvidence(
        [FromQuery] int page = 0,
        [FromQuery] int pageSize = 50,
        [FromQuery] string? sortBy = null,
        [FromQuery] string? sortDirection = "asc",
        CancellationToken cancellationToken = default)
    {
        var result = await _repository.GetPagedAsync(page, pageSize, sortBy, sortDirection, cancellationToken);
        return Ok(new PagedResult<EvidenceItemDto>
        {
            Items = _mapper.Map<IReadOnlyList<EvidenceItemDto>>(result.Items),
            TotalCount = result.TotalCount,
            Page = result.Page,
            PageSize = result.PageSize
        });
    }

    [HttpGet("{id:long}")]
    public async Task<ActionResult<EvidenceItemDto>> GetEvidenceItem(long id, CancellationToken cancellationToken)
    {
        var evidence = await _repository.GetWithDetailsAsync(id, cancellationToken);
        if (evidence == null) return NotFound();
        return Ok(_mapper.Map<EvidenceItemDto>(evidence));
    }
}
