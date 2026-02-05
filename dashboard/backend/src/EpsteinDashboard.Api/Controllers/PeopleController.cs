using AutoMapper;
using EpsteinDashboard.Application.DTOs;
using EpsteinDashboard.Application.Services;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Microsoft.AspNetCore.Mvc;

namespace EpsteinDashboard.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class PeopleController : ControllerBase
{
    private readonly IPersonRepository _repository;
    private readonly IRelationshipRepository _relationshipRepository;
    private readonly NetworkAnalysisService _networkService;
    private readonly IMapper _mapper;

    public PeopleController(
        IPersonRepository repository,
        IRelationshipRepository relationshipRepository,
        NetworkAnalysisService networkService,
        IMapper mapper)
    {
        _repository = repository;
        _relationshipRepository = relationshipRepository;
        _networkService = networkService;
        _mapper = mapper;
    }

    [HttpGet]
    public async Task<ActionResult<PagedResult<PersonListDto>>> GetPeople(
        [FromQuery] int page = 0,
        [FromQuery] int pageSize = 50,
        [FromQuery] string? search = null,
        [FromQuery] string? sortBy = null,
        [FromQuery] string? sortDirection = "asc",
        CancellationToken cancellationToken = default)
    {
        if (!string.IsNullOrEmpty(search))
        {
            var searchResult = await _repository.SearchByNameAsync(search, page, pageSize, cancellationToken);
            return Ok(new PagedResult<PersonListDto>
            {
                Items = _mapper.Map<IReadOnlyList<PersonListDto>>(searchResult.Items),
                TotalCount = searchResult.TotalCount,
                Page = searchResult.Page,
                PageSize = searchResult.PageSize
            });
        }

        var result = await _repository.GetPagedAsync(page, pageSize, sortBy, sortDirection, cancellationToken);
        return Ok(new PagedResult<PersonListDto>
        {
            Items = _mapper.Map<IReadOnlyList<PersonListDto>>(result.Items),
            TotalCount = result.TotalCount,
            Page = result.Page,
            PageSize = result.PageSize
        });
    }

    [HttpGet("{id:long}")]
    public async Task<ActionResult<PersonDetailDto>> GetPerson(long id, CancellationToken cancellationToken)
    {
        var person = await _repository.GetByIdWithRelationshipsAsync(id, cancellationToken);
        if (person == null) return NotFound();

        var dto = _mapper.Map<PersonDetailDto>(person);

        var allRelationships = person.RelationshipsAsPerson1
            .Concat(person.RelationshipsAsPerson2)
            .ToList();
        dto.Relationships = _mapper.Map<List<RelationshipDto>>(allRelationships);
        dto.RelationshipCount = allRelationships.Count;

        // Get counts for related entities
        var events = await _repository.GetEventsForPersonAsync(id, cancellationToken);
        dto.EventCount = events.Count;

        var documents = await _repository.GetDocumentsForPersonAsync(id, cancellationToken);
        dto.DocumentCount = documents.Count;

        var financials = await _repository.GetFinancialsForPersonAsync(id, cancellationToken);
        dto.FinancialTransactionCount = financials.Count;

        var media = await _repository.GetMediaForPersonAsync(id, cancellationToken);
        dto.MediaCount = media.Count;

        return Ok(dto);
    }

    [HttpGet("{id:long}/relationships")]
    public async Task<ActionResult<IReadOnlyList<RelationshipDto>>> GetRelationships(long id, CancellationToken cancellationToken)
    {
        var relationships = await _relationshipRepository.GetByPersonIdAsync(id, cancellationToken);
        return Ok(_mapper.Map<IReadOnlyList<RelationshipDto>>(relationships));
    }

    [HttpGet("{id:long}/events")]
    public async Task<ActionResult<IReadOnlyList<EventDto>>> GetEvents(long id, CancellationToken cancellationToken)
    {
        var events = await _repository.GetEventsForPersonAsync(id, cancellationToken);
        return Ok(_mapper.Map<IReadOnlyList<EventDto>>(events));
    }

    [HttpGet("{id:long}/documents")]
    public async Task<ActionResult<IReadOnlyList<DocumentListDto>>> GetDocuments(long id, CancellationToken cancellationToken)
    {
        var documents = await _repository.GetDocumentsForPersonAsync(id, cancellationToken);
        return Ok(_mapper.Map<IReadOnlyList<DocumentListDto>>(documents));
    }

    [HttpGet("{id:long}/financials")]
    public async Task<ActionResult<IReadOnlyList<FinancialTransactionDto>>> GetFinancials(long id, CancellationToken cancellationToken)
    {
        var transactions = await _repository.GetFinancialsForPersonAsync(id, cancellationToken);
        return Ok(_mapper.Map<IReadOnlyList<FinancialTransactionDto>>(transactions));
    }

    [HttpGet("{id:long}/media")]
    public async Task<ActionResult<IReadOnlyList<MediaFileDto>>> GetMedia(long id, CancellationToken cancellationToken)
    {
        var media = await _repository.GetMediaForPersonAsync(id, cancellationToken);
        return Ok(_mapper.Map<IReadOnlyList<MediaFileDto>>(media));
    }

    [HttpGet("{id:long}/network")]
    public async Task<ActionResult<NetworkGraphDto>> GetNetwork(long id, [FromQuery] int depth = 2, CancellationToken cancellationToken = default)
    {
        var graph = await _networkService.GetPersonNetworkAsync(id, depth, cancellationToken);
        return Ok(graph);
    }

    [HttpGet("connection")]
    public async Task<ActionResult<ConnectionPath>> FindConnection(
        [FromQuery] long person1Id,
        [FromQuery] long person2Id,
        [FromQuery] int maxDepth = 6,
        CancellationToken cancellationToken = default)
    {
        var path = await _networkService.FindConnectionAsync(person1Id, person2Id, maxDepth, cancellationToken);
        return Ok(path);
    }

    [HttpGet("frequencies")]
    public async Task<ActionResult<IReadOnlyList<EntityFrequencyDto>>> GetFrequencies(
        [FromQuery] int limit = 500,
        CancellationToken cancellationToken = default)
    {
        var results = await _repository.GetAllWithFrequenciesAsync(limit, cancellationToken);

        var dtos = results.Select(r => new EntityFrequencyDto
        {
            Id = r.Person.PersonId,
            Name = r.Person.FullName,
            EntityType = "person",
            PrimaryRole = r.Person.PrimaryRole,
            DocumentCount = r.DocumentCount,
            EventCount = r.EventCount,
            RelationshipCount = r.RelationshipCount,
            FinancialCount = r.FinancialCount,
            FinancialTotal = r.FinancialTotal,
            MediaCount = r.MediaCount,
            TotalMentions = r.DocumentCount + r.EventCount + r.RelationshipCount + r.FinancialCount + r.MediaCount
        }).ToList();

        return Ok(dtos);
    }
}
