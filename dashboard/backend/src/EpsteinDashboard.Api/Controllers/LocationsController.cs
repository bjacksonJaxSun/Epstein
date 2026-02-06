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
    public async Task<ActionResult<PagedResult<LocationListDto>>> GetLocations(
        [FromQuery] int page = 0,
        [FromQuery] int pageSize = 50,
        [FromQuery] string? search = null,
        [FromQuery] string? locationType = null,
        [FromQuery] string? country = null,
        [FromQuery] string? sortBy = null,
        [FromQuery] string? sortDirection = "desc",
        CancellationToken cancellationToken = default)
    {
        var result = await _repository.GetPagedWithCountsAsync(
            page, pageSize, search, locationType, country, sortBy, sortDirection, cancellationToken);

        var dtos = result.Items.Select(r => new LocationListDto
        {
            LocationId = r.Location.LocationId,
            LocationName = r.Location.LocationName,
            LocationType = r.Location.LocationType,
            City = r.Location.City,
            StateProvince = r.Location.StateProvince,
            Country = r.Location.Country,
            GpsLatitude = r.Location.Latitude,
            GpsLongitude = r.Location.Longitude,
            Description = r.Location.Description,
            Owner = r.OwnerName,
            EventCount = r.EventCount,
            MediaCount = r.MediaCount,
            EvidenceCount = r.EvidenceCount,
            TotalActivity = r.TotalActivity
        }).ToList();

        return Ok(new PagedResult<LocationListDto>
        {
            Items = dtos,
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

    [HttpGet("countries")]
    public async Task<ActionResult<IReadOnlyList<string>>> GetCountries(CancellationToken cancellationToken)
    {
        var result = await _repository.GetPagedWithCountsAsync(0, 1000, cancellationToken: cancellationToken);
        var countries = result.Items
            .Where(r => !string.IsNullOrWhiteSpace(r.Location.Country))
            .Select(r => r.Location.Country!)
            .Distinct()
            .OrderBy(c => c)
            .ToList();
        return Ok(countries);
    }

    [HttpGet("types")]
    public async Task<ActionResult<IReadOnlyList<string>>> GetLocationTypes(CancellationToken cancellationToken)
    {
        var result = await _repository.GetPagedWithCountsAsync(0, 1000, cancellationToken: cancellationToken);
        var types = result.Items
            .Where(r => !string.IsNullOrWhiteSpace(r.Location.LocationType))
            .Select(r => r.Location.LocationType!)
            .Distinct()
            .OrderBy(t => t)
            .ToList();
        return Ok(types);
    }

    [HttpGet("{id:long}/documents")]
    public async Task<ActionResult<IReadOnlyList<DocumentListDto>>> GetLocationDocuments(long id, CancellationToken cancellationToken)
    {
        var documents = await _repository.GetDocumentsForLocationAsync(id, cancellationToken);
        return Ok(_mapper.Map<IReadOnlyList<DocumentListDto>>(documents));
    }
}
