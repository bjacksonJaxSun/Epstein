using AutoMapper;
using EpsteinDashboard.Application.DTOs;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Microsoft.AspNetCore.Mvc;

namespace EpsteinDashboard.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class SearchController : ControllerBase
{
    private readonly ISearchService _searchService;
    private readonly IPersonRepository _personRepository;
    private readonly IMapper _mapper;

    public SearchController(ISearchService searchService, IPersonRepository personRepository, IMapper mapper)
    {
        _searchService = searchService;
        _personRepository = personRepository;
        _mapper = mapper;
    }

    [HttpGet]
    public async Task<ActionResult<PagedResult<SearchResultDto>>> Search(
        [FromQuery] string query,
        [FromQuery] int page = 0,
        [FromQuery] int pageSize = 50,
        [FromQuery] bool highlight = true,
        [FromQuery] string? dateFrom = null,
        [FromQuery] string? dateTo = null,
        [FromQuery] string? documentTypes = null,
        CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(query))
            return BadRequest("Query parameter is required.");

        var request = new SearchRequest
        {
            Query = query,
            Page = page,
            PageSize = pageSize,
            Highlight = highlight,
            DateFrom = dateFrom,
            DateTo = dateTo,
            DocumentTypes = documentTypes?.Split(',').ToList()
        };

        var result = await _searchService.SearchAsync(request, cancellationToken);
        return Ok(new PagedResult<SearchResultDto>
        {
            Items = _mapper.Map<IReadOnlyList<SearchResultDto>>(result.Items),
            TotalCount = result.TotalCount,
            Page = result.Page,
            PageSize = result.PageSize
        });
    }

    [HttpGet("entities")]
    public async Task<ActionResult<PagedResult<PersonListDto>>> SearchEntities(
        [FromQuery] string query,
        [FromQuery] int page = 0,
        [FromQuery] int pageSize = 50,
        CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(query))
            return BadRequest("Query parameter is required.");

        var result = await _personRepository.SearchByNameAsync(query, page, pageSize, cancellationToken);
        return Ok(new PagedResult<PersonListDto>
        {
            Items = _mapper.Map<IReadOnlyList<PersonListDto>>(result.Items),
            TotalCount = result.TotalCount,
            Page = result.Page,
            PageSize = result.PageSize
        });
    }

    [HttpGet("suggestions")]
    public async Task<ActionResult<IReadOnlyList<string>>> GetSuggestions(
        [FromQuery] string query,
        [FromQuery] int limit = 10,
        CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(query))
            return Ok(Array.Empty<string>());

        var suggestions = await _searchService.SuggestAsync(query, limit, cancellationToken);
        return Ok(suggestions);
    }
}
