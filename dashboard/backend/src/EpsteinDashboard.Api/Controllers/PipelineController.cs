using Microsoft.AspNetCore.Mvc;
using Npgsql;
using System.Diagnostics;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;

namespace EpsteinDashboard.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class PipelineController : ControllerBase
{
    private readonly string _connectionString;
    private readonly IWebHostEnvironment _env;

    public PipelineController(IConfiguration configuration, IWebHostEnvironment env)
    {
        _connectionString = configuration.GetConnectionString("DefaultConnection")
            ?? "Host=localhost;Database=epstein_documents;Username=epstein_user;Password=epstein_secure_pw_2024";
        _env = env;
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
                ActiveJobs = g.Where(w => w.SecondsSinceHeartbeat < 60).Sum(w => w.ActiveJobs),
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

        // Paused / stopped counts (supplementary — not in the view)
        await using (var cmd = new NpgsqlCommand(@"
            SELECT job_type,
              COUNT(*) FILTER (WHERE status = 'paused')  AS paused,
              COUNT(*) FILTER (WHERE status = 'stopped') AS stopped
            FROM job_pool
            WHERE status IN ('paused', 'stopped')
            GROUP BY job_type", conn))
        {
            await using var reader = await cmd.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                var jobType = reader.GetString(0);
                var paused  = reader.GetInt64(1);
                var stopped = reader.GetInt64(2);
                var summary = response.Summary.FirstOrDefault(s => s.JobType == jobType);
                if (summary != null)
                {
                    summary.Paused  = paused;
                    summary.Stopped = stopped;
                }
                else
                {
                    response.Summary.Add(new JobQueueSummary { JobType = jobType, Paused = paused, Stopped = stopped });
                }
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

    [HttpPost("job-types/{jobType}/pause")]
    public async Task<ActionResult> PauseJobType(string jobType)
    {
        await using var conn = new NpgsqlConnection(_connectionString);
        await conn.OpenAsync();
        await using var cmd = new NpgsqlCommand(
            "UPDATE job_pool SET status = 'paused', updated_at = NOW() WHERE job_type = @jobType AND status = 'pending'", conn);
        cmd.Parameters.AddWithValue("jobType", jobType);
        cmd.CommandTimeout = 300;
        var affected = await cmd.ExecuteNonQueryAsync();
        return Ok(new { success = true, affected });
    }

    [HttpPost("job-types/{jobType}/resume")]
    public async Task<ActionResult> ResumeJobType(string jobType)
    {
        await using var conn = new NpgsqlConnection(_connectionString);
        await conn.OpenAsync();
        await using var cmd = new NpgsqlCommand(
            "UPDATE job_pool SET status = 'pending', updated_at = NOW() WHERE job_type = @jobType AND status = 'paused'", conn);
        cmd.Parameters.AddWithValue("jobType", jobType);
        cmd.CommandTimeout = 300;
        var affected = await cmd.ExecuteNonQueryAsync();
        return Ok(new { success = true, affected });
    }

    [HttpPost("job-types/{jobType}/stop")]
    public async Task<ActionResult> StopJobType(string jobType)
    {
        await using var conn = new NpgsqlConnection(_connectionString);
        await conn.OpenAsync();
        await using var cmd = new NpgsqlCommand(
            "UPDATE job_pool SET status = 'stopped', updated_at = NOW() WHERE job_type = @jobType AND status IN ('pending', 'claimed', 'paused')", conn);
        cmd.Parameters.AddWithValue("jobType", jobType);
        cmd.CommandTimeout = 300;
        var affected = await cmd.ExecuteNonQueryAsync();
        return Ok(new { success = true, affected });
    }

    [HttpPost("job-types/{jobType}/retry-failed")]
    public async Task<ActionResult> RetryFailedJobs(string jobType)
    {
        await using var conn = new NpgsqlConnection(_connectionString);
        await conn.OpenAsync();
        await using var cmd = new NpgsqlCommand(@"
            UPDATE job_pool
            SET status = 'pending',
                updated_at = NOW(),
                error_message = NULL,
                claimed_by = NULL,
                started_at = NULL,
                completed_at = NULL
            WHERE job_type = @jobType AND status = 'failed'", conn);
        cmd.Parameters.AddWithValue("jobType", jobType);
        cmd.CommandTimeout = 300;
        var affected = await cmd.ExecuteNonQueryAsync();
        return Ok(new { success = true, affected });
    }

    [HttpPost("job-types/{jobType}/clear-stopped")]
    public async Task<ActionResult> ClearStoppedJobs(string jobType)
    {
        await using var conn = new NpgsqlConnection(_connectionString);
        await conn.OpenAsync();
        await using var cmd = new NpgsqlCommand(
            "DELETE FROM job_pool WHERE job_type = @jobType AND status IN ('stopped', 'paused')", conn);
        cmd.Parameters.AddWithValue("jobType", jobType);
        cmd.CommandTimeout = 300;
        var affected = await cmd.ExecuteNonQueryAsync();
        return Ok(new { success = true, affected });
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

    // ─── Launch Endpoints ───────────────────────────────────────────────────

    [HttpGet("launch/status")]
    public ActionResult<LaunchStatus> GetLaunchStatus()
    {
        var extractionDir = FindExtractionDir();
        bool Exists(string script) => extractionDir != null && System.IO.File.Exists(Path.Combine(extractionDir, script));

        return Ok(new LaunchStatus
        {
            ExtractionDirFound = extractionDir != null,
            Scripts = new Dictionary<string, bool>
            {
                ["submitExtractText"] = Exists("submit_extraction_jobs.py"),
                ["submitChunkEmbed"] = Exists("submit_chunk_embed_jobs.py"),
                ["startWorkers"] = Exists("start_extraction_workers.py"),
                ["startChunkWorkers"] = Exists("start_extraction_workers.py"),
                ["startEmbeddingServer"] = Exists("start_embedding_server.py"),
            }
        });
    }

    [HttpPost("launch/submit-extract-text")]
    public async Task<ActionResult<LaunchResult>> SubmitExtractTextJobs()
    {
        await using var conn = new NpgsqlConnection(_connectionString);
        await conn.OpenAsync();

        await using var cmd = new NpgsqlCommand(@"
            INSERT INTO job_pool (job_type, payload, priority, timeout_seconds, source_machine)
            SELECT
                'extract_text',
                jsonb_build_object('action', 'extract_text', 'document_id', document_id, 'r2_key', r2_key),
                0, 300, 'dashboard-api'
            FROM documents
            WHERE extraction_status = 'pending'
              AND r2_key IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM job_pool jp
                  WHERE jp.job_type = 'extract_text'
                    AND jp.status IN ('pending', 'claimed', 'running', 'paused')
                    AND (jp.payload->>'document_id')::bigint = documents.document_id
              )", conn);
        cmd.CommandTimeout = 300;
        var inserted = await cmd.ExecuteNonQueryAsync();

        return Ok(new LaunchResult
        {
            Success = true,
            Message = $"Submitted {inserted:N0} extract_text jobs to queue",
            JobsSubmitted = inserted,
        });
    }

    [HttpPost("launch/submit-chunk-embed")]
    public async Task<ActionResult<LaunchResult>> SubmitChunkEmbedJobs()
    {
        await using var conn = new NpgsqlConnection(_connectionString);
        await conn.OpenAsync();

        await using var cmd = new NpgsqlCommand(@"
            INSERT INTO job_pool (job_type, payload, priority, timeout_seconds, source_machine)
            SELECT
                'chunk_embed',
                jsonb_build_object('action', 'chunk_embed', 'document_id', document_id),
                0, 120, 'dashboard-api'
            FROM documents d
            WHERE NOT EXISTS (SELECT 1 FROM document_chunks c WHERE c.document_id = d.document_id)
              AND NOT EXISTS (
                  SELECT 1 FROM job_pool jp
                  WHERE jp.job_type = 'chunk_embed'
                    AND jp.status IN ('pending', 'claimed', 'running', 'paused')
                    AND (jp.payload->>'document_id')::bigint = d.document_id
              )
              AND ((d.full_text IS NOT NULL AND LENGTH(d.full_text) > 50)
                   OR (d.video_transcript IS NOT NULL AND LENGTH(d.video_transcript) > 10))", conn);
        cmd.CommandTimeout = 300;
        var inserted = await cmd.ExecuteNonQueryAsync();

        return Ok(new LaunchResult
        {
            Success = true,
            Message = $"Submitted {inserted:N0} chunk_embed jobs to queue",
            JobsSubmitted = inserted,
        });
    }

    [HttpPost("launch/start-workers")]
    public ActionResult<LaunchResult> StartExtractionWorkers()
    {
        var extractionDir = FindExtractionDir();
        if (extractionDir == null)
            return BadRequest(new LaunchResult { Success = false, Message = "epstein_extraction directory not found" });

        var scriptPath = Path.Combine(extractionDir, "start_extraction_workers.py");
        if (!System.IO.File.Exists(scriptPath))
            return BadRequest(new LaunchResult { Success = false, Message = "start_extraction_workers.py not found" });

        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = "python",
                Arguments = $"\"{scriptPath}\" --job-types extract_text",
                WorkingDirectory = extractionDir,
                UseShellExecute = false,
                CreateNoWindow = true,
            };
            psi.Environment["DATABASE_URL"] = GetPythonDbUrl();
            Process.Start(psi);
            return Ok(new LaunchResult { Success = true, Message = "Extraction worker process started in background" });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new LaunchResult { Success = false, Message = $"Failed to start process: {ex.Message}" });
        }
    }

    [HttpPost("launch/start-chunk-workers")]
    public async Task<ActionResult<LaunchResult>> StartChunkWorkers()
    {
        var extractionDir = FindExtractionDir();
        if (extractionDir == null)
            return BadRequest(new LaunchResult { Success = false, Message = "epstein_extraction directory not found" });

        var launcherScript = Path.Combine(extractionDir, "start_chunk_workers.py");
        if (!System.IO.File.Exists(launcherScript))
            return BadRequest(new LaunchResult { Success = false, Message = "start_chunk_workers.py not found" });

        var dbUrl = GetPythonDbUrl();
        var localPids = new List<int>();
        int remoteJobsSubmitted = 0;

        // 1. Start workers locally
        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = "python",
                Arguments = $"\"{launcherScript}\" --db-url \"{dbUrl}\"",
                WorkingDirectory = extractionDir,
                UseShellExecute = false,
                CreateNoWindow = true,
            };
            var proc = Process.Start(psi);
            if (proc != null) localPids.Add(proc.Id);
        }
        catch (Exception ex)
        {
            return StatusCode(500, new LaunchResult { Success = false, Message = $"Failed to start local process: {ex.Message}" });
        }

        // 2. Submit general jobs so remote machines start their own chunk workers
        try
        {
            await using var conn = new NpgsqlConnection(_connectionString);
            await conn.OpenAsync();

            // Find distinct remote hostnames with general workers (excluding this machine)
            var localHost = System.Net.Dns.GetHostName();
            await using var hostCmd = new NpgsqlCommand(@"
                SELECT DISTINCT SPLIT_PART(worker_id, ':', 1) as host
                FROM worker_heartbeat
                WHERE 'general' = ANY(job_types)
                  AND last_heartbeat > NOW() - INTERVAL '120 seconds'
                  AND SPLIT_PART(worker_id, ':', 1) != @local", conn);
            hostCmd.Parameters.AddWithValue("local", localHost);

            var remoteHosts = new List<string>();
            await using (var reader = await hostCmd.ExecuteReaderAsync())
                while (await reader.ReadAsync())
                    remoteHosts.Add(reader.GetString(0));

            foreach (var host in remoteHosts)
            {
                // Use Start-Process to spawn workers detached — pooled_job_worker.py already exists on all machines
                var psCmd = $"1..3 | ForEach-Object {{ Start-Process python -ArgumentList 'services\\pooled_job_worker.py','--job-types','chunk_embed','--max-concurrent','2','--batch-size','2','--db-url','{dbUrl}' -WindowStyle Hidden }}";
                var payload = System.Text.Json.JsonSerializer.Serialize(new
                {
                    action = "powershell",
                    command = psCmd,
                    timeout = 30
                });

                await using var insertCmd = new NpgsqlCommand(@"
                    INSERT INTO job_pool (job_type, payload, status, priority)
                    VALUES ('general', @payload::jsonb, 'pending', 10)", conn);
                insertCmd.Parameters.AddWithValue("payload", payload);
                await insertCmd.ExecuteNonQueryAsync();
                remoteJobsSubmitted++;
            }
        }
        catch (Exception ex)
        {
            // Remote submission failed but local started — partial success
            return Ok(new LaunchResult
            {
                Success = true,
                Message = $"Local workers started (PID {string.Join(", ", localPids)}). Remote submission failed: {ex.Message}"
            });
        }

        var msg = $"Local launcher started (PID {string.Join(", ", localPids)})";
        if (remoteJobsSubmitted > 0)
            msg += $"; submitted start jobs to {remoteJobsSubmitted} remote machine(s)";
        else
            msg += "; no remote general workers found";

        return Ok(new LaunchResult { Success = true, Message = msg });
    }

    [HttpPost("launch/rebuild-vector-index")]
    public async Task<ActionResult<LaunchResult>> RebuildVectorIndex()
    {
        await using var conn = new NpgsqlConnection(_connectionString);
        await conn.OpenAsync();

        // Count embedded chunks
        long embeddedChunks = 0;
        await using (var countCmd = new NpgsqlCommand(
            "SELECT COUNT(*) FROM document_chunks WHERE embedding_vector IS NOT NULL", conn))
            embeddedChunks = Convert.ToInt64(await countCmd.ExecuteScalarAsync() ?? 0);

        // Check if index already exists
        bool indexExists = false;
        await using (var checkCmd = new NpgsqlCommand(@"
            SELECT COUNT(*) FROM pg_indexes
            WHERE tablename = 'document_chunks'
              AND indexname = 'idx_document_chunks_embedding'", conn))
            indexExists = Convert.ToInt64(await checkCmd.ExecuteScalarAsync() ?? 0) > 0;

        string sql;
        string msg;
        if (indexExists)
        {
            sql = "REINDEX INDEX CONCURRENTLY idx_document_chunks_embedding";
            msg = $"Rebuilt HNSW vector index on {embeddedChunks:N0} embedded chunks";
        }
        else
        {
            sql = "CREATE INDEX CONCURRENTLY idx_document_chunks_embedding ON document_chunks USING hnsw (embedding_vector vector_cosine_ops) WITH (m=16, ef_construction=64)";
            msg = $"Created HNSW vector index on {embeddedChunks:N0} embedded chunks";
        }

        await using var cmd = new NpgsqlCommand(sql, conn);
        cmd.CommandTimeout = 3600; // index rebuild can take minutes
        await cmd.ExecuteNonQueryAsync();

        return Ok(new LaunchResult { Success = true, Message = msg });
    }

    [HttpPost("launch/start-embedding-server")]
    public ActionResult<LaunchResult> StartEmbeddingServer()
    {
        var extractionDir = FindExtractionDir();
        if (extractionDir == null)
            return BadRequest(new LaunchResult { Success = false, Message = "epstein_extraction directory not found" });

        var scriptPath = Path.Combine(extractionDir, "start_embedding_server.py");
        if (!System.IO.File.Exists(scriptPath))
            return BadRequest(new LaunchResult { Success = false, Message = "start_embedding_server.py not found" });

        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = "python",
                Arguments = $"\"{scriptPath}\"",
                WorkingDirectory = extractionDir,
                UseShellExecute = false,
                CreateNoWindow = true,
            };
            Process.Start(psi);
            return Ok(new LaunchResult { Success = true, Message = "Embedding server process started in background" });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new LaunchResult { Success = false, Message = $"Failed to start process: {ex.Message}" });
        }
    }

    private string? FindExtractionDir()
    {
        var dir = new DirectoryInfo(_env.ContentRootPath);
        while (dir != null)
        {
            var candidate = Path.Combine(dir.FullName, "epstein_extraction");
            if (System.IO.Directory.Exists(candidate)) return candidate;
            dir = dir.Parent;
        }
        return null;
    }

    private string GetPythonDbUrl()
    {
        var builder = new NpgsqlConnectionStringBuilder(_connectionString);
        var parts = new List<string>();
        if (!string.IsNullOrEmpty(builder.Host)) parts.Add($"host={builder.Host}");
        if (builder.Port > 0 && builder.Port != 5432) parts.Add($"port={builder.Port}");
        if (!string.IsNullOrEmpty(builder.Database)) parts.Add($"dbname={builder.Database}");
        if (!string.IsNullOrEmpty(builder.Username)) parts.Add($"user={builder.Username}");
        if (!string.IsNullOrEmpty(builder.Password)) parts.Add($"password={builder.Password}");
        return string.Join(" ", parts);
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
    public long Paused { get; set; }
    public long Stopped { get; set; }
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

public class LaunchStatus
{
    public bool ExtractionDirFound { get; set; }
    public Dictionary<string, bool> Scripts { get; set; } = new();
}

public class LaunchResult
{
    public bool Success { get; set; }
    public string Message { get; set; } = "";
    public int JobsSubmitted { get; set; }
}
