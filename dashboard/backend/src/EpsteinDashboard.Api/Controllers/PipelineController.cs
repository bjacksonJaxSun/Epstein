using Microsoft.AspNetCore.Mvc;
using Npgsql;
using System.Text.Json.Serialization;
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

    [HttpGet("nodes")]
    public async Task<ActionResult<List<NodeInfo>>> GetNodes()
    {
        var workers = new List<WorkerInfo>();
        await using var conn = new NpgsqlConnection(_connectionString);
        await conn.OpenAsync();

        await using var cmd = new NpgsqlCommand(@"
            SELECT worker_id, hostname, code_version, job_types, status,
                   active_jobs, started_at, last_heartbeat, pending_command,
                   EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) as seconds_since_heartbeat
            FROM worker_heartbeat
            ORDER BY hostname, worker_id", conn);

        await using var reader = await cmd.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            workers.Add(new WorkerInfo
            {
                WorkerId = reader.GetString(0),
                Hostname = reader.GetString(1),
                CodeVersion = reader.IsDBNull(2) ? null : reader.GetString(2),
                JobTypes = reader.IsDBNull(3) ? Array.Empty<string>() : reader.GetFieldValue<string[]>(3),
                Status = reader.IsDBNull(4) ? "unknown" : reader.GetString(4),
                ActiveJobs = reader.IsDBNull(5) ? 0 : reader.GetInt32(5),
                StartedAt = reader.IsDBNull(6) ? null : reader.GetDateTime(6),
                LastHeartbeat = reader.IsDBNull(7) ? null : reader.GetDateTime(7),
                PendingCommand = reader.IsDBNull(8) ? null : reader.GetString(8),
                SecondsSinceHeartbeat = reader.IsDBNull(9) ? 9999 : reader.GetDouble(9),
            });
        }

        var nodes = workers
            .GroupBy(w => w.Hostname)
            .Select(g => new NodeInfo
            {
                Hostname = g.Key,
                IsOnline = g.Any(w => w.SecondsSinceHeartbeat < 60),
                TotalWorkers = g.Count(),
                ActiveJobs = g.Sum(w => w.ActiveJobs),
                CodeVersion = g.FirstOrDefault(w => w.CodeVersion != null)?.CodeVersion,
                Workers = g.ToList(),
            })
            .OrderBy(n => n.Hostname)
            .ToList();

        return Ok(nodes);
    }

    [HttpGet("jobs")]
    public async Task<ActionResult<JobsResponse>> GetJobs()
    {
        var response = new JobsResponse();
        await using var conn = new NpgsqlConnection(_connectionString);
        await conn.OpenAsync();

        // Summary by type from job_pool_progress view
        await using (var cmd = new NpgsqlCommand("SELECT * FROM job_pool_progress", conn))
        {
            await using var reader = await cmd.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                response.Summary.Add(new JobQueueSummary
                {
                    JobType = reader["job_type"]?.ToString() ?? "",
                    Pending = Convert.ToInt64(reader["pending"]),
                    Claimed = Convert.ToInt64(reader["claimed"]),
                    Running = Convert.ToInt64(reader["running"]),
                    Completed = Convert.ToInt64(reader["completed"]),
                    Failed = Convert.ToInt64(reader["failed"]),
                    Skipped = Convert.ToInt64(reader["skipped"]),
                    Total = Convert.ToInt64(reader["total"]),
                    PctComplete = Convert.ToDouble(reader["pct_complete"]),
                });
            }
        }

        // Throughput (last 5 min, per type)
        await using (var cmd = new NpgsqlCommand(@"
            SELECT job_type, COUNT(*) as completed_5min
            FROM job_pool
            WHERE status = 'completed' AND updated_at > NOW() - INTERVAL '5 minutes'
            GROUP BY job_type", conn))
        {
            await using var reader = await cmd.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                var jobType = reader.GetString(0);
                var count = reader.GetInt64(1);
                var summary = response.Summary.FirstOrDefault(s => s.JobType == jobType);
                if (summary != null) summary.Completed5Min = count;
            }
        }

        // Recent errors
        await using (var cmd = new NpgsqlCommand(@"
            SELECT job_id, job_type, error_message, completed_at, claimed_by
            FROM job_pool
            WHERE status IN ('failed','skipped') AND error_message IS NOT NULL
            ORDER BY completed_at DESC NULLS LAST
            LIMIT 20", conn))
        {
            await using var reader = await cmd.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                response.Errors.Add(new JobError
                {
                    JobId = reader.GetInt64(0),
                    JobType = reader.GetString(1),
                    ErrorMessage = reader.IsDBNull(2) ? "" : reader.GetString(2),
                    CompletedAt = reader.IsDBNull(3) ? null : reader.GetDateTime(3),
                    ClaimedBy = reader.IsDBNull(4) ? null : reader.GetString(4),
                });
            }
        }

        return Ok(response);
    }

    [HttpGet("kpis")]
    public async Task<ActionResult<PipelineKpis>> GetKpis()
    {
        var kpis = new PipelineKpis();
        await using var conn = new NpgsqlConnection(_connectionString);
        await conn.OpenAsync();

        // Overall throughput (1min, 5min, 15min windows)
        await using (var cmd = new NpgsqlCommand(@"
            SELECT
              COUNT(*) FILTER (WHERE updated_at > NOW() - INTERVAL '1 minute') as completed_1min,
              COUNT(*) FILTER (WHERE updated_at > NOW() - INTERVAL '5 minutes') as completed_5min,
              COUNT(*) FILTER (WHERE updated_at > NOW() - INTERVAL '15 minutes') as completed_15min
            FROM job_pool WHERE status = 'completed'", conn))
        {
            await using var reader = await cmd.ExecuteReaderAsync();
            if (await reader.ReadAsync())
            {
                kpis.Completed1Min = reader.GetInt64(0);
                kpis.Completed5Min = reader.GetInt64(1);
                kpis.Completed15Min = reader.GetInt64(2);
            }
        }

        // Per-machine throughput (5min)
        await using (var cmd = new NpgsqlCommand(@"
            SELECT SPLIT_PART(claimed_by, ':', 1) as hostname, COUNT(*) as completed_5min
            FROM job_pool WHERE status = 'completed' AND updated_at > NOW() - INTERVAL '5 minutes'
            GROUP BY SPLIT_PART(claimed_by, ':', 1)", conn))
        {
            await using var reader = await cmd.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                kpis.PerMachineThroughput.Add(new MachineThroughput
                {
                    Hostname = reader.GetString(0),
                    Completed5Min = reader.GetInt64(1),
                });
            }
        }

        // Average job duration (last 15 min completed)
        await using (var cmd = new NpgsqlCommand(@"
            SELECT job_type,
                   AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration_sec,
                   MIN(EXTRACT(EPOCH FROM (completed_at - started_at))) as min_duration_sec,
                   MAX(EXTRACT(EPOCH FROM (completed_at - started_at))) as max_duration_sec
            FROM job_pool
            WHERE status = 'completed' AND started_at IS NOT NULL AND completed_at IS NOT NULL
              AND completed_at > NOW() - INTERVAL '15 minutes'
            GROUP BY job_type", conn))
        {
            await using var reader = await cmd.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                kpis.AvgDuration.Add(new JobDuration
                {
                    JobType = reader.GetString(0),
                    AvgSec = reader.IsDBNull(1) ? 0 : reader.GetDouble(1),
                    MinSec = reader.IsDBNull(2) ? 0 : reader.GetDouble(2),
                    MaxSec = reader.IsDBNull(3) ? 0 : reader.GetDouble(3),
                });
            }
        }

        // ETA calculation
        await using (var cmd = new NpgsqlCommand(@"
            SELECT job_type,
              COUNT(*) FILTER (WHERE status = 'pending') as pending,
              COUNT(*) FILTER (WHERE status = 'completed' AND updated_at > NOW() - INTERVAL '5 minutes') as rate_5min
            FROM job_pool GROUP BY job_type", conn))
        {
            await using var reader = await cmd.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                var pending = reader.GetInt64(1);
                var rate5Min = reader.GetInt64(2);
                double? etaMinutes = rate5Min > 0 ? (double)pending / rate5Min * 5.0 : null;

                kpis.QueueEta.Add(new QueueEta
                {
                    JobType = reader.GetString(0),
                    Pending = pending,
                    Rate5Min = rate5Min,
                    EtaMinutes = etaMinutes,
                });
            }
        }

        return Ok(kpis);
    }

    [HttpGet("throughput-history")]
    public async Task<ActionResult<List<ThroughputBucket>>> GetThroughputHistory(
        [FromQuery] int minutes = 30, [FromQuery] int bucketSeconds = 60)
    {
        minutes = Math.Clamp(minutes, 1, 1440);
        bucketSeconds = Math.Clamp(bucketSeconds, 10, 3600);

        var buckets = new List<ThroughputBucket>();
        await using var conn = new NpgsqlConnection(_connectionString);
        await conn.OpenAsync();

        await using var cmd = new NpgsqlCommand(@"
            SELECT
              date_trunc('second', completed_at) - (EXTRACT(EPOCH FROM completed_at)::int % @bucket) * INTERVAL '1 second' AS bucket,
              SPLIT_PART(claimed_by, ':', 1) AS hostname,
              COUNT(*) AS completed
            FROM job_pool
            WHERE status = 'completed'
              AND completed_at IS NOT NULL
              AND completed_at > NOW() - @minutes * INTERVAL '1 minute'
            GROUP BY bucket, hostname
            ORDER BY bucket", conn);
        cmd.Parameters.AddWithValue("bucket", bucketSeconds);
        cmd.Parameters.AddWithValue("minutes", minutes);

        await using var reader = await cmd.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            buckets.Add(new ThroughputBucket
            {
                Timestamp = reader.GetDateTime(0),
                Hostname = reader.GetString(1),
                Completed = reader.GetInt64(2),
            });
        }

        return Ok(buckets);
    }

    [HttpPost("nodes/{hostname}/command")]
    public async Task<ActionResult> SendNodeCommand(string hostname, [FromBody] CommandRequest request)
    {
        var allowed = new[] { "shutdown", "restart", "kill_children" };
        if (!allowed.Contains(request.Command))
            return BadRequest(new { error = $"Invalid command. Allowed: {string.Join(", ", allowed)}" });

        await using var conn = new NpgsqlConnection(_connectionString);
        await conn.OpenAsync();

        await using var cmd = new NpgsqlCommand("SELECT send_host_command(@hostname, @command)", conn);
        cmd.Parameters.AddWithValue("hostname", hostname);
        cmd.Parameters.AddWithValue("command", request.Command);
        await cmd.ExecuteScalarAsync();

        return Ok(new { success = true, message = $"Command '{request.Command}' sent to all workers on {hostname}" });
    }

    [HttpPost("workers/{workerId}/command")]
    public async Task<ActionResult> SendWorkerCommand(string workerId, [FromBody] CommandRequest request)
    {
        var allowed = new[] { "shutdown", "restart", "kill_children" };
        if (!allowed.Contains(request.Command))
            return BadRequest(new { error = $"Invalid command. Allowed: {string.Join(", ", allowed)}" });

        await using var conn = new NpgsqlConnection(_connectionString);
        await conn.OpenAsync();

        await using var cmd = new NpgsqlCommand("SELECT send_worker_command(@worker_id, @command)", conn);
        cmd.Parameters.AddWithValue("worker_id", workerId);
        cmd.Parameters.AddWithValue("command", request.Command);
        await cmd.ExecuteScalarAsync();

        return Ok(new { success = true, message = $"Command '{request.Command}' sent to worker {workerId}" });
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

// --- Existing DTOs ---

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

// --- New DTOs for distributed workload management ---

public class NodeInfo
{
    public string Hostname { get; set; } = "";
    public bool IsOnline { get; set; }
    public int TotalWorkers { get; set; }
    public int ActiveJobs { get; set; }
    public string? CodeVersion { get; set; }
    public List<WorkerInfo> Workers { get; set; } = new();
}

public class WorkerInfo
{
    public string WorkerId { get; set; } = "";
    [JsonIgnore]
    public string Hostname { get; set; } = "";
    public string Status { get; set; } = "unknown";
    public int ActiveJobs { get; set; }
    public string[] JobTypes { get; set; } = Array.Empty<string>();
    public DateTime? LastHeartbeat { get; set; }
    public double SecondsSinceHeartbeat { get; set; }
    public DateTime? StartedAt { get; set; }
    public string? CodeVersion { get; set; }
    public string? PendingCommand { get; set; }
}

public class JobsResponse
{
    public List<JobQueueSummary> Summary { get; set; } = new();
    public List<JobError> Errors { get; set; } = new();
}

public class JobQueueSummary
{
    public string JobType { get; set; } = "";
    public long Pending { get; set; }
    public long Claimed { get; set; }
    public long Running { get; set; }
    public long Completed { get; set; }
    public long Failed { get; set; }
    public long Skipped { get; set; }
    public long Total { get; set; }
    public double PctComplete { get; set; }
    public long Completed5Min { get; set; }
}

public class JobError
{
    public long JobId { get; set; }
    public string JobType { get; set; } = "";
    public string ErrorMessage { get; set; } = "";
    public DateTime? CompletedAt { get; set; }
    public string? ClaimedBy { get; set; }
}

public class PipelineKpis
{
    public long Completed1Min { get; set; }
    public long Completed5Min { get; set; }
    public long Completed15Min { get; set; }
    public List<MachineThroughput> PerMachineThroughput { get; set; } = new();
    public List<JobDuration> AvgDuration { get; set; } = new();
    public List<QueueEta> QueueEta { get; set; } = new();
}

public class MachineThroughput
{
    public string Hostname { get; set; } = "";
    public long Completed5Min { get; set; }
}

public class JobDuration
{
    public string JobType { get; set; } = "";
    public double AvgSec { get; set; }
    public double MinSec { get; set; }
    public double MaxSec { get; set; }
}

public class QueueEta
{
    public string JobType { get; set; } = "";
    public long Pending { get; set; }
    public long Rate5Min { get; set; }
    public double? EtaMinutes { get; set; }
}

public class CommandRequest
{
    public string Command { get; set; } = "";
}

public class ThroughputBucket
{
    public DateTime Timestamp { get; set; }
    public string Hostname { get; set; } = "";
    public long Completed { get; set; }
}
