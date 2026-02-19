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
        _connectionString = configuration.GetConnectionString("DefaultConnection")
            ?? "Host=localhost;Database=epstein_documents;Username=epstein_user;Password=epstein_secure_pw_2024";
    }

    [HttpGet("status")]
    public async Task<ActionResult<PipelineStatus>> GetStatus()
    {
        var status = new PipelineStatus();
        await using var conn = new NpgsqlConnection(_connectionString);
        await conn.OpenAsync();

        await using (var cmd = new NpgsqlCommand("SELECT COUNT(*) FROM documents", conn))
            status.TotalDocuments = Convert.ToInt64(await cmd.ExecuteScalarAsync() ?? 0);

        await using (var cmd = new NpgsqlCommand("SELECT COUNT(*) FROM documents WHERE full_text IS NOT NULL AND LENGTH(full_text) > 50", conn))
            status.DocumentsWithText = Convert.ToInt64(await cmd.ExecuteScalarAsync() ?? 0);

        await using (var cmd = new NpgsqlCommand("SELECT COUNT(*) FROM document_chunks", conn))
            status.TotalChunks = Convert.ToInt64(await cmd.ExecuteScalarAsync() ?? 0);

        await using (var cmd = new NpgsqlCommand("SELECT COUNT(*) FROM document_chunks WHERE embedding_vector IS NOT NULL", conn))
            status.ChunksWithEmbeddings = Convert.ToInt64(await cmd.ExecuteScalarAsync() ?? 0);

        await using (var cmd = new NpgsqlCommand("SELECT COUNT(*) FROM documents WHERE video_path IS NOT NULL", conn))
            status.TotalMediaFiles = Convert.ToInt64(await cmd.ExecuteScalarAsync() ?? 0);

        await using (var cmd = new NpgsqlCommand("SELECT COUNT(*) FROM documents WHERE video_transcript IS NOT NULL AND LENGTH(video_transcript) > 10", conn))
            status.MediaFilesTranscribed = Convert.ToInt64(await cmd.ExecuteScalarAsync() ?? 0);

        status.TranscriptionStatus = await GetTranscriptionStatusAsync();
        status.OcrStatus = await GetOcrStatusAsync();
        status.ApiStatus = GetApiStatus();
        status.DatabaseStatus = await GetDatabaseStatusAsync(conn);

        return Ok(status);
    }

    private async Task<TranscriptionStatus> GetTranscriptionStatusAsync()
    {
        var status = new TranscriptionStatus();
        try
        {
            var logPath = "/tmp/transcription.log";
            if (!System.IO.File.Exists(logPath)) { status.Status = "not_started"; return status; }
            var lines = await System.IO.File.ReadAllLinesAsync(logPath);
            foreach (var line in lines.TakeLast(50).Reverse())
            {
                var match = Regex.Match(line, @"Processing: (\d+)/(\d+) \| Success: (\d+) \| Failed: (\d+)");
                if (match.Success)
                {
                    status.ProcessedFiles = int.Parse(match.Groups[1].Value);
                    status.TotalFiles = int.Parse(match.Groups[2].Value);
                    status.SuccessCount = int.Parse(match.Groups[3].Value);
                    status.FailedCount = int.Parse(match.Groups[4].Value);
                    status.PercentComplete = status.TotalFiles > 0 ? (double)status.ProcessedFiles / status.TotalFiles * 100 : 0;
                    status.Status = status.ProcessedFiles >= status.TotalFiles ? "complete" : "running";
                    break;
                }
            }
            status.LastUpdate = System.IO.File.GetLastWriteTimeUtc(logPath);
        }
        catch { status.Status = "error"; }
        return status;
    }

    private async Task<OcrStatus> GetOcrStatusAsync()
    {
        var status = new OcrStatus();
        try
        {
            var logPath = "/tmp/ocr.log";
            if (!System.IO.File.Exists(logPath)) { status.Status = "not_started"; return status; }
            status.LastUpdate = System.IO.File.GetLastWriteTimeUtc(logPath);
            status.Status = "complete";
        }
        catch { status.Status = "error"; }
        return status;
    }

    private ServiceStatus GetApiStatus() => new ServiceStatus
    {
        Status = "running",
        Uptime = (long)(DateTime.UtcNow - System.Diagnostics.Process.GetCurrentProcess().StartTime.ToUniversalTime()).TotalSeconds
    };

    private async Task<ServiceStatus> GetDatabaseStatusAsync(NpgsqlConnection conn)
    {
        var status = new ServiceStatus { Status = "running" };
        try
        {
            await using var cmd = new NpgsqlCommand("SELECT pg_database_size('epstein_documents')", conn);
            status.DatabaseSizeBytes = Convert.ToInt64(await cmd.ExecuteScalarAsync() ?? 0);
        }
        catch { status.Status = "error"; }
        return status;
    }
}

public class PipelineStatus
{
    public long TotalDocuments { get; set; }
    public long DocumentsWithText { get; set; }
    public long TotalChunks { get; set; }
    public long ChunksWithEmbeddings { get; set; }
    public long TotalMediaFiles { get; set; }
    public long MediaFilesTranscribed { get; set; }
    public OcrStatus OcrStatus { get; set; } = new();
    public TranscriptionStatus TranscriptionStatus { get; set; } = new();
    public ServiceStatus ApiStatus { get; set; } = new();
    public ServiceStatus DatabaseStatus { get; set; } = new();
}

public class OcrStatus
{
    public string Status { get; set; } = "unknown";
    public int ProcessedDocuments { get; set; }
    public int TotalDocuments { get; set; }
    public int SuccessCount { get; set; }
    public int FailedCount { get; set; }
    public double PercentComplete { get; set; }
    public DateTime? LastUpdate { get; set; }
}

public class TranscriptionStatus
{
    public string Status { get; set; } = "unknown";
    public int ProcessedFiles { get; set; }
    public int TotalFiles { get; set; }
    public int SuccessCount { get; set; }
    public int FailedCount { get; set; }
    public double PercentComplete { get; set; }
    public DateTime? LastUpdate { get; set; }
}

public class ServiceStatus
{
    public string Status { get; set; } = "unknown";
    public long Uptime { get; set; }
    public long DatabaseSizeBytes { get; set; }
}
