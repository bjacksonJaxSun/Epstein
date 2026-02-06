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
        [FromQuery] string? sortDirection = "desc",
        CancellationToken cancellationToken = default)
    {
        var result = await _repository.GetPagedWithCountsAsync(page, pageSize, search, sortBy, sortDirection, cancellationToken);

        var dtos = result.Items.Select(r => new PersonListDto
        {
            PersonId = r.Person.PersonId,
            FullName = r.Person.FullName,
            PrimaryRole = r.Person.PrimaryRole,
            Occupation = r.Person.Occupation,
            Nationality = r.Person.Nationality,
            ConfidenceLevel = r.Person.ConfidenceLevel,
            DocumentCount = r.DocumentCount,
            EventCount = r.EventCount,
            RelationshipCount = r.RelationshipCount,
            FinancialCount = r.FinancialCount,
            TotalMentions = r.TotalMentions,
            EpsteinRelationship = r.EpsteinRelationship
        }).ToList();

        return Ok(new PagedResult<PersonListDto>
        {
            Items = dtos,
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

    [HttpGet("duplicates")]
    public async Task<ActionResult<IReadOnlyList<DuplicateGroupDto>>> GetDuplicates(
        CancellationToken cancellationToken = default)
    {
        var duplicates = await _repository.FindDuplicatesAsync(0.8, cancellationToken);

        var dtos = duplicates.Select(g => new DuplicateGroupDto
        {
            CanonicalName = g.CanonicalName,
            Variants = g.Variants.Select(p => new PersonListDto
            {
                PersonId = p.PersonId,
                FullName = p.FullName,
                PrimaryRole = p.PrimaryRole,
                Occupation = p.Occupation,
                Nationality = p.Nationality,
                ConfidenceLevel = p.ConfidenceLevel
            }).ToList()
        }).ToList();

        return Ok(dtos);
    }

    [HttpPost("merge")]
    public async Task<ActionResult> MergePersons(
        [FromBody] MergePersonsRequest request,
        CancellationToken cancellationToken = default)
    {
        if (request.PrimaryPersonId <= 0 || request.MergePersonIds.Count == 0)
        {
            return BadRequest("Invalid merge request");
        }

        await _repository.MergePersonsAsync(request.PrimaryPersonId, request.MergePersonIds, cancellationToken);
        return Ok(new { message = $"Merged {request.MergePersonIds.Count} persons into {request.PrimaryPersonId}" });
    }
}
