using AutoMapper;
using EpsteinDashboard.Application.DTOs;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Microsoft.AspNetCore.Mvc;

namespace EpsteinDashboard.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class RelationshipsController : ControllerBase
{
    private readonly IRelationshipRepository _repository;
    private readonly IMapper _mapper;

    public RelationshipsController(IRelationshipRepository repository, IMapper mapper)
    {
        _repository = repository;
        _mapper = mapper;
    }

    [HttpGet]
    public async Task<ActionResult<PagedResult<RelationshipDto>>> GetRelationships(
        [FromQuery] int page = 0,
        [FromQuery] int pageSize = 50,
        [FromQuery] string? sortBy = null,
        [FromQuery] string? sortDirection = "asc",
        CancellationToken cancellationToken = default)
    {
        var result = await _repository.GetPagedAsync(page, pageSize, sortBy, sortDirection, cancellationToken);
        return Ok(new PagedResult<RelationshipDto>
        {
            Items = _mapper.Map<IReadOnlyList<RelationshipDto>>(result.Items),
            TotalCount = result.TotalCount,
            Page = result.Page,
            PageSize = result.PageSize
        });
    }

    [HttpGet("{id:long}")]
    public async Task<ActionResult<RelationshipDto>> GetRelationship(long id, CancellationToken cancellationToken)
    {
        var rel = await _repository.GetByIdAsync(id, cancellationToken);
        if (rel == null) return NotFound();
        return Ok(_mapper.Map<RelationshipDto>(rel));
    }
}
