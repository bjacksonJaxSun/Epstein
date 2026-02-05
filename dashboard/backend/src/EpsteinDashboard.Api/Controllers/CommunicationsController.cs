using AutoMapper;
using EpsteinDashboard.Application.DTOs;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Microsoft.AspNetCore.Mvc;

namespace EpsteinDashboard.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class CommunicationsController : ControllerBase
{
    private readonly ICommunicationRepository _repository;
    private readonly IMapper _mapper;

    public CommunicationsController(ICommunicationRepository repository, IMapper mapper)
    {
        _repository = repository;
        _mapper = mapper;
    }

    [HttpGet]
    public async Task<ActionResult<PagedResult<CommunicationDto>>> GetCommunications(
        [FromQuery] int page = 0,
        [FromQuery] int pageSize = 50,
        [FromQuery] string? communicationType = null,
        [FromQuery] string? sortBy = null,
        [FromQuery] string? sortDirection = "asc",
        CancellationToken cancellationToken = default)
    {
        var result = await _repository.GetFilteredAsync(page, pageSize, communicationType, sortBy, sortDirection, cancellationToken);
        return Ok(new PagedResult<CommunicationDto>
        {
            Items = _mapper.Map<IReadOnlyList<CommunicationDto>>(result.Items),
            TotalCount = result.TotalCount,
            Page = result.Page,
            PageSize = result.PageSize
        });
    }

    [HttpGet("{id:long}")]
    public async Task<ActionResult<CommunicationDto>> GetCommunication(long id, CancellationToken cancellationToken)
    {
        var comm = await _repository.GetWithRecipientsAsync(id, cancellationToken);
        if (comm == null) return NotFound();
        return Ok(_mapper.Map<CommunicationDto>(comm));
    }

    [HttpGet("{id:long}/recipients")]
    public async Task<ActionResult<IReadOnlyList<CommunicationRecipientDto>>> GetRecipients(long id, CancellationToken cancellationToken)
    {
        var comm = await _repository.GetWithRecipientsAsync(id, cancellationToken);
        if (comm == null) return NotFound();
        return Ok(_mapper.Map<IReadOnlyList<CommunicationRecipientDto>>(comm.Recipients));
    }
}
