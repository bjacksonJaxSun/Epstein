using AutoMapper;
using EpsteinDashboard.Application.DTOs;
using EpsteinDashboard.Core.Interfaces;
using EpsteinDashboard.Core.Models;
using Microsoft.AspNetCore.Mvc;

namespace EpsteinDashboard.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class DocumentsController : ControllerBase
{
    private readonly IDocumentRepository _repository;
    private readonly IMapper _mapper;

    public DocumentsController(IDocumentRepository repository, IMapper mapper)
    {
        _repository = repository;
        _mapper = mapper;
    }

    [HttpGet]
    public async Task<ActionResult<PagedResult<DocumentListDto>>> GetDocuments(
        [FromQuery] int page = 0,
        [FromQuery] int pageSize = 50,
        [FromQuery] string? documentType = null,
        [FromQuery] string? dateFrom = null,
        [FromQuery] string? dateTo = null,
        [FromQuery] string? sortBy = null,
        [FromQuery] string? sortDirection = "asc",
        CancellationToken cancellationToken = default)
    {
        var result = await _repository.GetFilteredAsync(page, pageSize, documentType, dateFrom, dateTo, sortBy, sortDirection, cancellationToken);
        return Ok(new PagedResult<DocumentListDto>
        {
            Items = _mapper.Map<IReadOnlyList<DocumentListDto>>(result.Items),
            TotalCount = result.TotalCount,
            Page = result.Page,
            PageSize = result.PageSize
        });
    }

    [HttpGet("{id:long}")]
    public async Task<ActionResult<DocumentDto>> GetDocument(long id, CancellationToken cancellationToken)
    {
        var document = await _repository.GetByIdAsync(id, cancellationToken);
        if (document == null) return NotFound();
        return Ok(_mapper.Map<DocumentDto>(document));
    }

    [HttpGet("{id:long}/entities")]
    public async Task<ActionResult<DocumentDto>> GetDocumentEntities(long id, CancellationToken cancellationToken)
    {
        var document = await _repository.GetWithEntitiesAsync(id, cancellationToken);
        if (document == null) return NotFound();
        return Ok(_mapper.Map<DocumentDto>(document));
    }

    [HttpGet("types")]
    public async Task<ActionResult<IReadOnlyList<string>>> GetDocumentTypes(CancellationToken cancellationToken)
    {
        var types = await _repository.GetDocumentTypesAsync(cancellationToken);
        return Ok(types);
    }

    [HttpGet("efta/{eftaNumber}")]
    public async Task<ActionResult<DocumentDto>> GetByEftaNumber(string eftaNumber, CancellationToken cancellationToken)
    {
        var document = await _repository.GetByEftaNumberAsync(eftaNumber, cancellationToken);
        if (document == null) return NotFound();
        return Ok(_mapper.Map<DocumentDto>(document));
    }

    private static readonly string EpsteinFilesPath = @"C:\Development\EpsteinDownloader\epstein_files";

    [HttpGet("{id:long}/file")]
    public async Task<IActionResult> GetDocumentFile(long id, CancellationToken cancellationToken)
    {
        var document = await _repository.GetByIdAsync(id, cancellationToken);
        if (document == null) return NotFound("Document not found");

        var filePath = document.FilePath;
        if (string.IsNullOrEmpty(filePath))
            return NotFound("Document file path not available");

        // Handle path remapping if file doesn't exist at original path
        if (!System.IO.File.Exists(filePath))
        {
            // Try remapping from old JaxSun path to new path
            var remappedPath = filePath.Replace(
                @"C:\Development\JaxSun.Ideas\tools\EpsteinDownloader\",
                @"C:\Development\EpsteinDownloader\");

            if (System.IO.File.Exists(remappedPath))
            {
                filePath = remappedPath;
            }
            // Search epstein_files subdirectories by EFTA number
            else if (!string.IsNullOrEmpty(document.EftaNumber))
            {
                var foundPath = FindFileByEfta(document.EftaNumber);
                if (foundPath != null)
                {
                    filePath = foundPath;
                }
                else
                {
                    return NotFound($"Document file not found for {document.EftaNumber}");
                }
            }
            else
            {
                return NotFound($"Document file not found at: {filePath}");
            }
        }

        var fileStream = System.IO.File.OpenRead(filePath);
        var contentType = "application/pdf";
        var fileName = Path.GetFileName(filePath);

        return File(fileStream, contentType, fileName);
    }

    private static string? FindFileByEfta(string eftaNumber)
    {
        var fileName = $"{eftaNumber}.pdf";

        // Search all subdirectories in epstein_files
        if (Directory.Exists(EpsteinFilesPath))
        {
            var files = Directory.GetFiles(EpsteinFilesPath, fileName, SearchOption.AllDirectories);
            if (files.Length > 0)
            {
                return files[0];
            }
        }

        return null;
    }
}
