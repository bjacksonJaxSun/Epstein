using EpsteinDashboard.Application.DTOs;
using EpsteinDashboard.Core.Models;
using EpsteinDashboard.Infrastructure.Data;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace EpsteinDashboard.Api.Controllers;

[ApiController]
[Route("api/vision")]
public class VisionAnalysisController : ControllerBase
{
    private readonly EpsteinDbContext _context;

    public VisionAnalysisController(EpsteinDbContext context)
    {
        _context = context;
    }

    [HttpGet("stats")]
    public async Task<ActionResult<VisionAnalysisStatsDto>> GetStats(CancellationToken cancellationToken)
    {
        var totalImages = await _context.MediaFiles.CountAsync(cancellationToken);
        var totalFaceDetections = await _context.FaceDetections.CountAsync(cancellationToken);
        var totalFaceClusters = await _context.FaceClusters.CountAsync(cancellationToken);
        var totalClassifications = await _context.DocumentClassifications.CountAsync(cancellationToken);

        var documentCount = await _context.DocumentClassifications.CountAsync(x => x.IsDocument, cancellationToken);
        var photoCount = await _context.DocumentClassifications.CountAsync(x => x.IsPhoto, cancellationToken);
        var withHandwriting = await _context.DocumentClassifications.CountAsync(x => x.HasHandwriting, cancellationToken);
        var withSignatures = await _context.DocumentClassifications.CountAsync(x => x.HasSignature, cancellationToken);

        var docTypeCounts = (await _context.DocumentClassifications
            .Where(x => x.DocumentType != null)
            .Select(x => x.DocumentType)
            .ToListAsync(cancellationToken))
            .GroupBy(x => x)
            .Select(g => new DocumentTypeCountDto(g.Key!, g.Count()))
            .OrderByDescending(x => x.Count)
            .ToList();

        return Ok(new VisionAnalysisStatsDto(
            totalImages,
            totalFaceDetections,
            totalFaceClusters,
            totalClassifications,
            documentCount,
            photoCount,
            withHandwriting,
            withSignatures,
            docTypeCounts
        ));
    }

    [HttpGet("faces")]
    public async Task<ActionResult<PagedResult<FaceDetectionDto>>> GetFaceDetections(
        [FromQuery] int page = 0,
        [FromQuery] int pageSize = 50,
        [FromQuery] long? clusterId = null,
        CancellationToken cancellationToken = default)
    {
        var query = _context.FaceDetections
            .Include(x => x.MediaFile)
            .Include(x => x.Cluster)
            .AsQueryable();

        if (clusterId.HasValue)
            query = query.Where(x => x.ClusterId == clusterId);

        var totalCount = await query.CountAsync(cancellationToken);

        var items = await query
            .OrderByDescending(x => x.CreatedAt)
            .Skip(page * pageSize)
            .Take(pageSize)
            .Select(x => new FaceDetectionDto(
                x.FaceId,
                x.MediaFileId,
                x.MediaFile != null ? x.MediaFile.FilePath : null,
                x.FaceIndex,
                x.BoundingBox,
                x.ClusterId,
                x.Cluster != null ? x.Cluster.PersonName : null,
                x.Confidence,
                x.CreatedAt
            ))
            .ToListAsync(cancellationToken);

        return Ok(new PagedResult<FaceDetectionDto>
        {
            Items = items,
            TotalCount = totalCount,
            Page = page,
            PageSize = pageSize
        });
    }

    [HttpGet("clusters")]
    public async Task<ActionResult<PagedResult<FaceClusterDto>>> GetFaceClusters(
        [FromQuery] int page = 0,
        [FromQuery] int pageSize = 50,
        [FromQuery] bool? named = null,
        CancellationToken cancellationToken = default)
    {
        var query = _context.FaceClusters.AsQueryable();

        if (named == true)
            query = query.Where(x => x.PersonName != null);
        else if (named == false)
            query = query.Where(x => x.PersonName == null);

        var totalCount = await query.CountAsync(cancellationToken);

        var items = await query
            .OrderByDescending(x => x.FaceCount)
            .Skip(page * pageSize)
            .Take(pageSize)
            .Select(x => new FaceClusterDto(
                x.ClusterId,
                x.PersonName,
                x.PersonId,
                x.FaceCount,
                x.RepresentativeFaceId,
                null, // Will be populated separately if needed
                x.CreatedAt
            ))
            .ToListAsync(cancellationToken);

        return Ok(new PagedResult<FaceClusterDto>
        {
            Items = items,
            TotalCount = totalCount,
            Page = page,
            PageSize = pageSize
        });
    }

    [HttpGet("clusters/{id:long}")]
    public async Task<ActionResult<FaceClusterDetailDto>> GetFaceCluster(long id, CancellationToken cancellationToken)
    {
        var cluster = await _context.FaceClusters
            .Where(x => x.ClusterId == id)
            .FirstOrDefaultAsync(cancellationToken);

        if (cluster == null) return NotFound();

        var faces = await _context.FaceDetections
            .Include(x => x.MediaFile)
            .Where(x => x.ClusterId == id)
            .Select(x => new FaceDetectionDto(
                x.FaceId,
                x.MediaFileId,
                x.MediaFile != null ? x.MediaFile.FilePath : null,
                x.FaceIndex,
                x.BoundingBox,
                x.ClusterId,
                cluster.PersonName,
                x.Confidence,
                x.CreatedAt
            ))
            .ToListAsync(cancellationToken);

        return Ok(new FaceClusterDetailDto(
            cluster.ClusterId,
            cluster.PersonName,
            cluster.PersonId,
            cluster.FaceCount,
            faces,
            cluster.CreatedAt
        ));
    }

    [HttpPut("clusters/{id:long}/name")]
    public async Task<ActionResult> UpdateClusterName(long id, [FromBody] UpdateClusterNameRequest request, CancellationToken cancellationToken)
    {
        var cluster = await _context.FaceClusters.FindAsync(new object[] { id }, cancellationToken);
        if (cluster == null) return NotFound();

        cluster.PersonName = request.Name;
        cluster.UpdatedAt = DateTime.UtcNow;

        await _context.SaveChangesAsync(cancellationToken);

        return Ok();
    }

    [HttpGet("classifications")]
    public async Task<ActionResult<PagedResult<DocumentClassificationDto>>> GetClassifications(
        [FromQuery] int page = 0,
        [FromQuery] int pageSize = 50,
        [FromQuery] string? documentType = null,
        [FromQuery] bool? isDocument = null,
        [FromQuery] bool? hasHandwriting = null,
        [FromQuery] bool? hasSignature = null,
        CancellationToken cancellationToken = default)
    {
        var query = _context.DocumentClassifications
            .Include(x => x.MediaFile)
            .AsQueryable();

        if (!string.IsNullOrEmpty(documentType))
            query = query.Where(x => x.DocumentType == documentType);
        if (isDocument.HasValue)
            query = query.Where(x => x.IsDocument == isDocument.Value);
        if (hasHandwriting == true)
            query = query.Where(x => x.HasHandwriting);
        if (hasSignature == true)
            query = query.Where(x => x.HasSignature);

        var totalCount = await query.CountAsync(cancellationToken);

        var items = await query
            .OrderByDescending(x => x.CreatedAt)
            .Skip(page * pageSize)
            .Take(pageSize)
            .Select(x => new DocumentClassificationDto(
                x.ClassificationId,
                x.MediaFileId,
                x.MediaFile != null ? x.MediaFile.FilePath : null,
                x.IsDocument,
                x.IsPhoto,
                x.DocumentType,
                x.DocumentSubtype,
                x.HasHandwriting,
                x.HasSignature,
                x.HasLetterhead,
                x.HasStamp,
                x.TextDensity,
                x.Confidence,
                x.CreatedAt
            ))
            .ToListAsync(cancellationToken);

        return Ok(new PagedResult<DocumentClassificationDto>
        {
            Items = items,
            TotalCount = totalCount,
            Page = page,
            PageSize = pageSize
        });
    }

    [HttpGet("classifications/types")]
    public async Task<ActionResult<IReadOnlyList<DocumentTypeCountDto>>> GetClassificationTypes(CancellationToken cancellationToken)
    {
        var types = (await _context.DocumentClassifications
            .Where(x => x.DocumentType != null)
            .Select(x => x.DocumentType)
            .ToListAsync(cancellationToken))
            .GroupBy(x => x)
            .Select(g => new DocumentTypeCountDto(g.Key!, g.Count()))
            .OrderByDescending(x => x.Count)
            .ToList();

        return Ok(types);
    }

    [HttpGet("import-status")]
    public async Task<ActionResult<ImportStatusDto>> GetImportStatus(CancellationToken cancellationToken)
    {
        var totalDocuments = await _context.Documents.CountAsync(cancellationToken);
        var totalMediaFiles = await _context.MediaFiles.CountAsync(cancellationToken);
        var totalPages = await _context.Documents.SumAsync(x => x.PageCount ?? 0, cancellationToken);
        var totalSizeBytes = await _context.Documents.SumAsync(x => x.FileSizeBytes ?? 0, cancellationToken);

        var lastDocument = await _context.Documents
            .OrderByDescending(x => x.CreatedAt)
            .Select(x => new { x.EftaNumber, x.FilePath, x.CreatedAt })
            .FirstOrDefaultAsync(cancellationToken);

        var extractionStats = await _context.Documents
            .GroupBy(x => x.ExtractionStatus)
            .Select(g => new { Status = g.Key, Count = g.Count() })
            .ToListAsync(cancellationToken);

        // OCR stats
        var documentsWithText = await _context.Documents
            .CountAsync(x => x.FullText != null && x.FullText.Length > 100, cancellationToken);

        var documentsNeedingOcr = await _context.Documents
            .CountAsync(x => x.ExtractionStatus == "partial", cancellationToken);

        // Documents with images are the OCR target population
        var totalDocsWithImages = await _context.MediaFiles
            .Where(m => m.MediaType == "image")
            .Select(m => m.SourceDocumentId)
            .Distinct()
            .CountAsync(cancellationToken);

        return Ok(new ImportStatusDto(
            totalDocuments,
            502700, // Expected total for dataset 10
            totalMediaFiles,
            totalPages,
            totalSizeBytes,
            lastDocument?.EftaNumber,
            lastDocument?.FilePath,
            lastDocument?.CreatedAt,
            extractionStats.ToDictionary(x => x.Status ?? "unknown", x => x.Count),
            documentsWithText,
            documentsNeedingOcr,
            totalDocsWithImages
        ));
    }
}

public record UpdateClusterNameRequest(string? Name);
