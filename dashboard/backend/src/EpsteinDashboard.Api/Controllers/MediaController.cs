using AutoMapper;
using EpsteinDashboard.Application.DTOs;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Microsoft.AspNetCore.Mvc;

namespace EpsteinDashboard.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class MediaController : ControllerBase
{
    private readonly IMediaRepository _repository;
    private readonly IMapper _mapper;

    public MediaController(IMediaRepository repository, IMapper mapper)
    {
        _repository = repository;
        _mapper = mapper;
    }

    [HttpGet]
    public async Task<ActionResult<PagedResult<MediaFileDto>>> GetMediaFiles(
        [FromQuery] int page = 0,
        [FromQuery] int pageSize = 50,
        [FromQuery] string? mediaType = null,
        [FromQuery] string? sortBy = null,
        [FromQuery] string? sortDirection = "asc",
        CancellationToken cancellationToken = default)
    {
        var result = await _repository.GetFilteredAsync(page, pageSize, mediaType, sortBy, sortDirection, cancellationToken);
        return Ok(new PagedResult<MediaFileDto>
        {
            Items = _mapper.Map<IReadOnlyList<MediaFileDto>>(result.Items),
            TotalCount = result.TotalCount,
            Page = result.Page,
            PageSize = result.PageSize
        });
    }

    [HttpGet("{id:long}")]
    public async Task<ActionResult<MediaFileDto>> GetMediaFile(long id, CancellationToken cancellationToken)
    {
        var media = await _repository.GetWithAnalysisAsync(id, cancellationToken);
        if (media == null) return NotFound();
        return Ok(_mapper.Map<MediaFileDto>(media));
    }

    [HttpGet("{id:long}/analysis")]
    public async Task<ActionResult<IReadOnlyList<ImageAnalysisDto>>> GetAnalysis(long id, CancellationToken cancellationToken)
    {
        var analyses = await _repository.GetAnalysesForMediaAsync(id, cancellationToken);
        return Ok(_mapper.Map<IReadOnlyList<ImageAnalysisDto>>(analyses));
    }

    [HttpGet("{id:long}/file")]
    public async Task<IActionResult> GetFile(long id, CancellationToken cancellationToken)
    {
        var media = await _repository.GetByIdAsync(id, cancellationToken);
        if (media == null) return NotFound();

        if (string.IsNullOrEmpty(media.FilePath) || !System.IO.File.Exists(media.FilePath))
            return NotFound("File not found on disk.");

        var contentType = media.MediaType?.ToLowerInvariant() switch
        {
            "image" => media.FileFormat?.ToLowerInvariant() switch
            {
                "jpg" or "jpeg" => "image/jpeg",
                "png" => "image/png",
                "gif" => "image/gif",
                "webp" => "image/webp",
                _ => "application/octet-stream"
            },
            "video" => "video/mp4",
            "audio" => "audio/mpeg",
            "document" => "application/pdf",
            _ => "application/octet-stream"
        };

        var stream = System.IO.File.OpenRead(media.FilePath);
        return File(stream, contentType, media.FileName ?? Path.GetFileName(media.FilePath));
    }
}
