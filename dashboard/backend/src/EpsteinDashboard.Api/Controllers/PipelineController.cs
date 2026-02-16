using Microsoft.AspNetCore.Mvc;
using Npgsql;
using System.Text.RegularExpressions;

namespace EpsteinDashboard.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class PipelineController : ControllerBase
{
    private readonly string _connectionString;

    public PipelineController(IConfiguration configuration)
    {
        _connectionString = configuration.GetConnectionString("EpsteinDb")
            ?? "Host=localhost;Database=epstein_documents;Username=epstein_user;Password=epstein_secure_pw_2024";
    }

    [HttpGet("status")]
    public async Task<ActionResult<PipelineStatus>> GetStatus()
    {
        var status = new PipelineStatus();

        await using var conn = new NpgsqlConnection(_connectionString);
        await conn.OpenAsync();

        await using (var cmd = new NpgsqlCommand("SELECT COUNT(*) FROM documents", conn))
        {
            status.TotalDocuments = Convert.ToInt64(await cmd.ExecuteScalarAsync() ?? 0);
        }

        await using (var cmd = new NpgsqlCommand(
            "SELECT COUNT(*) FROM documents WHERE full_text IS NOT NULL AND LENGTH(full_text) > 50", conn))
        {
            status.DocumentsWithText = Convert.ToInt64(await cmd.ExecuteScalarAsync() ?? 0);
        }

        await using (var cmd = new NpgsqlCommand(
            "SELECT COUNT(*) FROM documents WHERE (full_text IS NULL OR LENGTH(COALESCE(full_text, '')) < 100) AND extraction_status != 'error'", conn))
        {
            status.DocumentsNeedingOcr = Convert.ToInt64(await cmd.ExecuteScalarAsync() ?? 0);
        }

        await using (var cmd = new NpgsqlCommand("SELECT COUNT(*) FROM document_chunks", conn))
        {
            status.TotalChunks = Convert.ToInt64(await cmd.ExecuteScalarAsync() ?? 0);
        }

        await using (var cmd = new NpgsqlCommand(
            "SELECT COUNT(*) FROM document_chunks WHERE embedding_vector IS NOT NULL", conn))
        {
            status.ChunksWithEmbeddings = Convert.ToInt64(await cmd.ExecuteScalarAsync() ?? 0);
        }

        await using (var cmd = new NpgsqlCommand("SELECT COUNT(*) FROM media_files WHERE media_type = 'image'", conn))
        {
            status.TotalImages = Convert.ToInt64(await cmd.ExecuteScalarAsync() ?? 0);
        }

        status.DownloadStatus = await GetDownloadStatusAsync();
        status.EmbeddingStatus = await GetEmbeddingStatusAsync();
        status.ImportStatus = await GetImportStatusAsync();
        status.OcrStatus = await GetOcrStatusAsync(conn);
        status.ImageExtractionStatus = await GetImageExtractionStatusAsync();
        status.ApiStatus = GetApiStatus();
        status.DatabaseStatus = await GetDatabaseStatusAsync(conn);

        return Ok(status);
    }

    private async Task<DownloadStatus> GetDownloadStatusAsync()
    {
        var status = new DownloadStatus();
        try
        {
            var logPath = "/data/epstein_extraction/download_all.log";
            if (!System.IO.File.Exists(logPath))
            {
                status.Status = "not_started";
                return status;
            }

            var lines = await System.IO.File.ReadAllLinesAsync(logPath);
            var recentLines = lines.TakeLast(50).ToList();

            foreach (var line in recentLines.AsEnumerable().Reverse())
            {
                var downloadMatch = Regex.Match(line, @"Progress: (\d+)/(\d+) - OK: (\d+), Err: (\d+)");
                if (downloadMatch.Success)
                {
                    status.CurrentFile = int.Parse(downloadMatch.Groups[1].Value);
                    status.TotalFiles = int.Parse(downloadMatch.Groups[2].Value);
                    status.FilesDownloaded = int.Parse(downloadMatch.Groups[3].Value);
                    status.FilesErrored = int.Parse(downloadMatch.Groups[4].Value);
                    status.PercentComplete = status.TotalFiles > 0 ? (double)status.CurrentFile / status.TotalFiles * 100 : 0;
                    // Mark as complete if at 100%, otherwise downloading
                    status.Status = status.PercentComplete >= 100 ? "complete" : "downloading";
                    break;
                }

                var pageMatch = Regex.Match(line, @"Page (\d+)/(\d+): (\d+) files total");
                if (pageMatch.Success)
                {
                    status.CurrentPage = int.Parse(pageMatch.Groups[1].Value);
                    status.TotalPages = int.Parse(pageMatch.Groups[2].Value);
                    status.FilesFound = int.Parse(pageMatch.Groups[3].Value);
                    status.Status = "scraping";
                    status.PercentComplete = status.TotalPages > 0 ? (double)status.CurrentPage / status.TotalPages * 100 : 0;
                    break;
                }

                if (line.Contains("COMPLETE"))
                {
                    status.Status = "complete";
                    status.PercentComplete = 100;
                    break;
                }
            }

            status.LastUpdate = System.IO.File.GetLastWriteTimeUtc(logPath);
        }
        catch
        {
            status.Status = "error";
        }
        return status;
    }

    private async Task<EmbeddingStatus> GetEmbeddingStatusAsync()
    {
        var status = new EmbeddingStatus();
        try
        {
            var logPath = "/tmp/embeddings.log";
            if (!System.IO.File.Exists(logPath))
            {
                status.Status = "not_started";
                return status;
            }

            var lines = await System.IO.File.ReadAllLinesAsync(logPath);
            var recentLines = lines.TakeLast(20).ToList();

            foreach (var line in recentLines.AsEnumerable().Reverse())
            {
                var match = Regex.Match(line, @"Progress: ([\d,]+)/([\d,]+) \(([\d.]+)%\) - ([\d.]+) chunks/sec");
                if (match.Success)
                {
                    status.ProcessedChunks = long.Parse(match.Groups[1].Value.Replace(",", ""));
                    status.TotalChunks = long.Parse(match.Groups[2].Value.Replace(",", ""));
                    status.PercentComplete = double.Parse(match.Groups[3].Value);
                    status.ChunksPerSecond = double.Parse(match.Groups[4].Value);
                    status.Status = "running";
                    break;
                }

                if (line.Contains("Embedding complete"))
                {
                    status.Status = "complete";
                    status.PercentComplete = 100;
                    break;
                }
            }

            status.LastUpdate = System.IO.File.GetLastWriteTimeUtc(logPath);
        }
        catch
        {
            status.Status = "error";
        }
        return status;
    }

    private async Task<ImportStatus> GetImportStatusAsync()
    {
        var status = new ImportStatus();
        try
        {
            var activeImportPath = "/tmp/import_progress.json";
            if (System.IO.File.Exists(activeImportPath))
            {
                var lastWrite = System.IO.File.GetLastWriteTimeUtc(activeImportPath);
                if ((DateTime.UtcNow - lastWrite).TotalSeconds < 60)
                {
                    var json = await System.IO.File.ReadAllTextAsync(activeImportPath);
                    var datasetMatch = Regex.Match(json, "\"dataset\"\\s*:\\s*\"([^\"]+)\"");
                    var importedMatch = Regex.Match(json, "\"imported\"\\s*:\\s*(\\d+)");
                    var totalMatch = Regex.Match(json, "\"total\"\\s*:\\s*(\\d+)");
                    var skippedMatch = Regex.Match(json, "\"skipped\"\\s*:\\s*(\\d+)");

                    if (datasetMatch.Success && totalMatch.Success)
                    {
                        status.CurrentDataset = datasetMatch.Groups[1].Value;
                        status.ImportedCount = importedMatch.Success ? int.Parse(importedMatch.Groups[1].Value) : 0;
                        status.TotalFiles = int.Parse(totalMatch.Groups[1].Value);
                        status.SkippedCount = skippedMatch.Success ? int.Parse(skippedMatch.Groups[1].Value) : 0;
                        status.PercentComplete = status.TotalFiles > 0
                            ? (double)(status.ImportedCount + status.SkippedCount) / status.TotalFiles * 100
                            : 0;
                        // Mark as complete if at 100%, otherwise running
                        status.Status = status.PercentComplete >= 100 ? "complete" : "running";
                        status.LastUpdate = lastWrite;
                        return status;
                    }
                }
            }

            var logPath = "/data/epstein_extraction/process_new_pdfs.log";
            if (!System.IO.File.Exists(logPath))
            {
                status.Status = "not_started";
                return status;
            }

            var lines = await System.IO.File.ReadAllLinesAsync(logPath);
            var recentLines = lines.TakeLast(30).ToList();

            foreach (var line in recentLines.AsEnumerable().Reverse())
            {
                var completeMatch = Regex.Match(line, @"Complete: imported (\d+), skipped (\d+)");
                if (completeMatch.Success)
                {
                    status.ImportedCount = int.Parse(completeMatch.Groups[1].Value);
                    status.SkippedCount = int.Parse(completeMatch.Groups[2].Value);
                    status.Status = "idle";
                    break;
                }
            }

            status.LastUpdate = System.IO.File.GetLastWriteTimeUtc(logPath);
        }
        catch
        {
            status.Status = "idle";
        }
        return status;
    }

    private async Task<OcrStatus> GetOcrStatusAsync(NpgsqlConnection conn)
    {
        var status = new OcrStatus();
        try
        {
            var logPath = "/tmp/ocr.log";
            if (!System.IO.File.Exists(logPath))
            {
                status.Status = "not_started";
                return status;
            }

            var lastWrite = System.IO.File.GetLastWriteTimeUtc(logPath);
            var isStale = (DateTime.UtcNow - lastWrite).TotalSeconds > 120;

            var lines = await System.IO.File.ReadAllLinesAsync(logPath);
            var recentLines = lines.TakeLast(50).ToList();

            DateTime? startTime = null;

            foreach (var line in recentLines)
            {
                var totalMatch = Regex.Match(line, @"Total documents needing OCR: (\d+)");
                if (totalMatch.Success)
                {
                    var tsMatch = Regex.Match(line, @"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})");
                    if (tsMatch.Success && startTime == null)
                    {
                        DateTime.TryParse(tsMatch.Groups[1].Value, out var ts);
                        startTime = ts;
                    }
                }
            }

            foreach (var line in recentLines.AsEnumerable().Reverse())
            {
                var progressMatch = Regex.Match(line, @"Progress: (\d+)/(\d+) \(OCR success: (\d+), failed: (\d+)\)");
                if (progressMatch.Success)
                {
                    status.ProcessedDocuments = int.Parse(progressMatch.Groups[1].Value);
                    status.SuccessCount = int.Parse(progressMatch.Groups[3].Value);
                    status.FailedCount = int.Parse(progressMatch.Groups[4].Value);

                    // Query database for actual remaining documents needing OCR
                    // This gives us an accurate total instead of the stale log value
                    await using (var cmd = new NpgsqlCommand(
                        "SELECT COUNT(*) FROM documents WHERE (full_text IS NULL OR LENGTH(COALESCE(full_text, '')) < 100) AND extraction_status != 'error'", conn))
                    {
                        var remaining = Convert.ToInt32(await cmd.ExecuteScalarAsync() ?? 0);
                        // Total = already processed + still remaining
                        status.TotalDocuments = status.ProcessedDocuments + remaining;
                    }

                    // Calculate actual percent complete
                    status.PercentComplete = status.TotalDocuments > 0
                        ? (double)status.ProcessedDocuments / status.TotalDocuments * 100
                        : 0;

                    // Determine status based on progress and staleness
                    if (status.PercentComplete >= 100)
                    {
                        status.Status = isStale ? "complete" : "running";
                    }
                    else
                    {
                        status.Status = isStale ? "idle" : "running";
                    }

                    if (status.Status == "running" && status.ProcessedDocuments > 50 && startTime.HasValue)
                    {
                        var elapsed = DateTime.UtcNow - startTime.Value;
                        var remaining = Math.Max(0, status.TotalDocuments - status.ProcessedDocuments);
                        var docsPerSecond = status.ProcessedDocuments / elapsed.TotalSeconds;
                        if (docsPerSecond > 0 && remaining > 0)
                        {
                            status.EstimatedSecondsRemaining = (int)(remaining / docsPerSecond);
                            status.DocsPerMinute = docsPerSecond * 60;
                        }
                    }
                    break;
                }

                if (line.Contains("OCR complete") || line.Contains("Complete"))
                {
                    status.Status = "complete";
                    status.PercentComplete = 100;
                    break;
                }
            }

            status.LastUpdate = lastWrite;
        }
        catch
        {
            status.Status = "error";
        }
        return status;
    }

    private async Task<ImageExtractionStatus> GetImageExtractionStatusAsync()
    {
        var status = new ImageExtractionStatus();
        try
        {
            var logPath = "/tmp/image_extraction.log";
            if (!System.IO.File.Exists(logPath))
            {
                status.Status = "not_started";
                return status;
            }

            var lastWrite = System.IO.File.GetLastWriteTimeUtc(logPath);
            if ((DateTime.UtcNow - lastWrite).TotalSeconds > 120)
            {
                status.Status = "idle";
                status.LastUpdate = lastWrite;
                return status;
            }

            var lines = await System.IO.File.ReadAllLinesAsync(logPath);
            var recentLines = lines.TakeLast(50).ToList();

            DateTime? startTime = null;

            foreach (var line in recentLines)
            {
                if (line.Contains("Total documents needing image extraction:"))
                {
                    var tsMatch = Regex.Match(line, @"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})");
                    if (tsMatch.Success)
                    {
                        DateTime.TryParse(tsMatch.Groups[1].Value, out var ts);
                        startTime = ts;
                    }
                }
            }

            foreach (var line in recentLines.AsEnumerable().Reverse())
            {
                var progressMatch = Regex.Match(line, @"Progress: (\d+)/(\d+) \(Images: (\d+), Docs w/images: (\d+), Not in index: (\d+), Errors: (\d+)\)");
                if (progressMatch.Success)
                {
                    status.ProcessedDocuments = int.Parse(progressMatch.Groups[1].Value);
                    status.TotalDocuments = int.Parse(progressMatch.Groups[2].Value);
                    status.ImagesExtracted = int.Parse(progressMatch.Groups[3].Value);
                    status.DocsWithImages = int.Parse(progressMatch.Groups[4].Value);
                    status.NotInIndex = int.Parse(progressMatch.Groups[5].Value);
                    status.ErrorCount = int.Parse(progressMatch.Groups[6].Value);
                    status.Status = "running";
                    status.PercentComplete = status.TotalDocuments > 0
                        ? (double)status.ProcessedDocuments / status.TotalDocuments * 100
                        : 0;

                    if (status.ProcessedDocuments > 1000 && startTime.HasValue)
                    {
                        var elapsed = DateTime.UtcNow - startTime.Value;
                        var remaining = status.TotalDocuments - status.ProcessedDocuments;
                        var docsPerSecond = status.ProcessedDocuments / elapsed.TotalSeconds;
                        if (docsPerSecond > 0)
                        {
                            status.EstimatedSecondsRemaining = (int)(remaining / docsPerSecond);
                            status.DocsPerMinute = docsPerSecond * 60;
                        }
                    }
                    break;
                }

                if (line.Contains("Image extraction complete"))
                {
                    status.Status = "complete";
                    status.PercentComplete = 100;
                    break;
                }
            }

            status.LastUpdate = lastWrite;
        }
        catch
        {
            status.Status = "error";
        }
        return status;
    }

    private ServiceStatus GetApiStatus()
    {
        return new ServiceStatus
        {
            Status = "running",
            Uptime = (long)(DateTime.UtcNow - System.Diagnostics.Process.GetCurrentProcess().StartTime.ToUniversalTime()).TotalSeconds
        };
    }

    private async Task<ServiceStatus> GetDatabaseStatusAsync(NpgsqlConnection conn)
    {
        var status = new ServiceStatus { Status = "running" };
        try
        {
            await using var cmd = new NpgsqlCommand("SELECT pg_database_size('epstein_documents')", conn);
            var size = await cmd.ExecuteScalarAsync();
            status.DatabaseSizeBytes = Convert.ToInt64(size ?? 0);
        }
        catch
        {
            status.Status = "error";
        }
        return status;
    }
}

public class PipelineStatus
{
    public long TotalDocuments { get; set; }
    public long DocumentsWithText { get; set; }
    public long DocumentsNeedingOcr { get; set; }
    public long TotalChunks { get; set; }
    public long ChunksWithEmbeddings { get; set; }
    public long TotalImages { get; set; }
    public DownloadStatus DownloadStatus { get; set; } = new();
    public EmbeddingStatus EmbeddingStatus { get; set; } = new();
    public ImportStatus ImportStatus { get; set; } = new();
    public OcrStatus OcrStatus { get; set; } = new();
    public ImageExtractionStatus ImageExtractionStatus { get; set; } = new();
    public ServiceStatus ApiStatus { get; set; } = new();
    public ServiceStatus DatabaseStatus { get; set; } = new();
}

public class DownloadStatus
{
    public string Status { get; set; } = "unknown";
    public int CurrentDataset { get; set; }
    public int CurrentPage { get; set; }
    public int TotalPages { get; set; }
    public int CurrentFile { get; set; }
    public int TotalFiles { get; set; }
    public int FilesFound { get; set; }
    public int FilesDownloaded { get; set; }
    public int FilesErrored { get; set; }
    public double PercentComplete { get; set; }
    public int EstimatedSecondsRemaining { get; set; }
    public DateTime? LastUpdate { get; set; }
}

public class EmbeddingStatus
{
    public string Status { get; set; } = "unknown";
    public long ProcessedChunks { get; set; }
    public long TotalChunks { get; set; }
    public double PercentComplete { get; set; }
    public double ChunksPerSecond { get; set; }
    public int EstimatedSecondsRemaining { get; set; }
    public DateTime? LastUpdate { get; set; }
}

public class ImportStatus
{
    public string Status { get; set; } = "idle";
    public string? LastImportedFile { get; set; }
    public string? CurrentDataset { get; set; }
    public int ImportedCount { get; set; }
    public int SkippedCount { get; set; }
    public int TotalFiles { get; set; }
    public double PercentComplete { get; set; }
    public DateTime? LastUpdate { get; set; }
}

public class OcrStatus
{
    public string Status { get; set; } = "unknown";
    public int ProcessedDocuments { get; set; }
    public int TotalDocuments { get; set; }
    public int SuccessCount { get; set; }
    public int FailedCount { get; set; }
    public double PercentComplete { get; set; }
    public double DocsPerMinute { get; set; }
    public int EstimatedSecondsRemaining { get; set; }
    public DateTime? LastUpdate { get; set; }
}

public class ImageExtractionStatus
{
    public string Status { get; set; } = "unknown";
    public int ProcessedDocuments { get; set; }
    public int TotalDocuments { get; set; }
    public int ImagesExtracted { get; set; }
    public int DocsWithImages { get; set; }
    public int NotInIndex { get; set; }
    public int ErrorCount { get; set; }
    public double PercentComplete { get; set; }
    public double DocsPerMinute { get; set; }
    public int EstimatedSecondsRemaining { get; set; }
    public DateTime? LastUpdate { get; set; }
}

public class ServiceStatus
{
    public string Status { get; set; } = "unknown";
    public long Uptime { get; set; }
    public long DatabaseSizeBytes { get; set; }
}
