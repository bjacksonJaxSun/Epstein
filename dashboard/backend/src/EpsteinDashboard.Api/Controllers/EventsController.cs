using AutoMapper;
using EpsteinDashboard.Application.DTOs;
using EpsteinDashboard.Application.Services;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Microsoft.AspNetCore.Mvc;

namespace EpsteinDashboard.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class EventsController : ControllerBase
{
    private readonly IEventRepository _repository;
    private readonly TimelineService _timelineService;
    private readonly IMapper _mapper;

    public EventsController(IEventRepository repository, TimelineService timelineService, IMapper mapper)
    {
        _repository = repository;
        _timelineService = timelineService;
        _mapper = mapper;
    }

    [HttpGet]
    public async Task<ActionResult<PagedResult<EventDto>>> GetEvents(
        [FromQuery] int page = 0,
        [FromQuery] int pageSize = 50,
        [FromQuery] string? eventType = null,
        [FromQuery] string? dateFrom = null,
        [FromQuery] string? dateTo = null,
        [FromQuery] string? sortBy = null,
        [FromQuery] string? sortDirection = "asc",
        CancellationToken cancellationToken = default)
    {
        var result = await _repository.GetFilteredAsync(page, pageSize, eventType, dateFrom, dateTo, sortBy, sortDirection, cancellationToken);
        return Ok(new PagedResult<EventDto>
        {
            Items = _mapper.Map<IReadOnlyList<EventDto>>(result.Items),
            TotalCount = result.TotalCount,
            Page = result.Page,
            PageSize = result.PageSize
        });
    }

    [HttpGet("{id:long}")]
    public async Task<ActionResult<EventDto>> GetEvent(long id, CancellationToken cancellationToken)
    {
        var evt = await _repository.GetWithParticipantsAsync(id, cancellationToken);
        if (evt == null) return NotFound();
        return Ok(_mapper.Map<EventDto>(evt));
    }

    [HttpGet("{id:long}/participants")]
    public async Task<ActionResult<IReadOnlyList<EventParticipantDto>>> GetParticipants(long id, CancellationToken cancellationToken)
    {
        var evt = await _repository.GetWithParticipantsAsync(id, cancellationToken);
        if (evt == null) return NotFound();
        return Ok(_mapper.Map<IReadOnlyList<EventParticipantDto>>(evt.Participants));
    }

    [HttpGet("timeline")]
    public async Task<ActionResult<PagedResult<TimelineEventDto>>> GetTimeline(
        [FromQuery] int page = 0,
        [FromQuery] int pageSize = 100,
        [FromQuery] string? eventType = null,
        [FromQuery] string? dateFrom = null,
        [FromQuery] string? dateTo = null,
        CancellationToken cancellationToken = default)
    {
        var result = await _timelineService.GetTimelineAsync(page, pageSize, eventType, dateFrom, dateTo, cancellationToken);
        return Ok(new PagedResult<TimelineEventDto>
        {
            Items = _mapper.Map<IReadOnlyList<TimelineEventDto>>(result.Items),
            TotalCount = result.TotalCount,
            Page = result.Page,
            PageSize = result.PageSize
        });
    }
}
