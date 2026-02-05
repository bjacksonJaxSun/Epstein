using AutoMapper;
using EpsteinDashboard.Application.DTOs;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Microsoft.AspNetCore.Mvc;

namespace EpsteinDashboard.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class LocationsController : ControllerBase
{
    private readonly ILocationRepository _repository;
    private readonly IMapper _mapper;

    public LocationsController(ILocationRepository repository, IMapper mapper)
    {
        _repository = repository;
        _mapper = mapper;
    }

    [HttpGet]
    public async Task<ActionResult<PagedResult<LocationDto>>> GetLocations(
        [FromQuery] int page = 0,
        [FromQuery] int pageSize = 50,
        [FromQuery] string? sortBy = null,
        [FromQuery] string? sortDirection = "asc",
        CancellationToken cancellationToken = default)
    {
        var result = await _repository.GetPagedAsync(page, pageSize, sortBy, sortDirection, cancellationToken);
        return Ok(new PagedResult<LocationDto>
        {
            Items = _mapper.Map<IReadOnlyList<LocationDto>>(result.Items),
            TotalCount = result.TotalCount,
            Page = result.Page,
            PageSize = result.PageSize
        });
    }

    [HttpGet("{id:long}")]
    public async Task<ActionResult<LocationDto>> GetLocation(long id, CancellationToken cancellationToken)
    {
        var location = await _repository.GetWithDetailsAsync(id, cancellationToken);
        if (location == null) return NotFound();
        return Ok(_mapper.Map<LocationDto>(location));
    }
}
