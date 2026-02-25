# Remote Worker Skill

Execute commands, manage processes, and transfer files on remote machines via Tailscale.

## When to Use

Use this skill when the user wants to:
- Run commands on a remote machine (bobbyhomeep)
- Start or stop processes remotely
- Transfer files to/from the remote worker
- Check remote machine status (CPU, memory)
- Execute long-running tasks on another machine

## Setup (One-time)

Import the client module before using any commands:

```powershell
Import-Module "D:\Personal\Epstein\remote-worker\scripts\RemoteWorkerClient.ps1"
```

## Available Commands

### Check Worker Status
```powershell
Get-RemoteStatus
```
Returns CPU%, memory%, hostname, and timestamp.

### Execute PowerShell Commands
```powershell
Invoke-RemotePowerShell "Get-Process | Select -First 5"
Invoke-RemotePowerShell "Get-ChildItem C:\Temp" -Timeout 120
```

### Execute CMD Commands
```powershell
Invoke-RemoteCmd "dir C:\Temp"
Invoke-RemoteCmd "ipconfig /all"
```

### Start a Process
```powershell
# Simple process start
Start-RemoteProcess "notepad.exe"

# With arguments and working directory
Start-RemoteProcess "python.exe" -Arguments "C:\scripts\long_task.py" -WorkingDirectory "C:\scripts"
```

### Stop a Process
```powershell
Stop-RemoteProcess -ProcessName "notepad"
Stop-RemoteProcess -ProcessId 1234
```

### File Transfer
```powershell
# Upload file to remote
Send-FileToWorker -LocalPath "C:\local\script.py" -RemotePath "C:\Temp\script.py"

# Download file from remote
Get-FileFromWorker -RemotePath "C:\Temp\results.csv" -LocalPath "C:\local\results.csv"
```

### Low-Level Command (Advanced)
```powershell
# Send any supported action
Send-RemoteCommand -Action powershell -Command "Get-Date" -Timeout 60

# Fire-and-forget (don't wait for result)
Send-RemoteCommand -Action process-start -Command "python.exe" -Wait:$false
```

## Configuration

Default worker: **bobbyhomeep** at Tailscale IP `100.75.137.22`

Network shares:
- Commands: `\\100.75.137.22\RemoteWorker\commands`
- Results: `\\100.75.137.22\RemoteWorker\results`
- Logs: `\\100.75.137.22\RemoteWorker\logs`

## Common Patterns

### Run Python Script Remotely
```powershell
Import-Module "D:\Personal\Epstein\remote-worker\scripts\RemoteWorkerClient.ps1"
Start-RemoteProcess "python.exe" -Arguments "D:\scripts\download_worker.py --dataset 11" -WorkingDirectory "D:\scripts"
```

### Check What's Running
```powershell
Invoke-RemotePowerShell "Get-Process python, dotnet -ErrorAction SilentlyContinue | Select ProcessName, Id, CPU, WorkingSet"
```

### View Remote Logs
```powershell
Invoke-RemotePowerShell "Get-Content 'C:\ProgramData\RemoteWorker\logs\worker-$(Get-Date -Format yyyy-MM-dd).log' -Tail 20"
```

### Kill Stuck Process
```powershell
Stop-RemoteProcess -ProcessName "python"
```

## Service Management (Remote Updates)

### Get Service Version
```powershell
Get-RemoteWorkerVersion
# Returns: scriptHash, lastModified, workerName
```

### Push Service Update
```powershell
# Update remote worker with local script
Update-RemoteWorkerService

# Or specify a specific script file
Update-RemoteWorkerService -ScriptPath "D:\scripts\RemoteWorkerService.ps1"
```

### Rollback to Previous Version
```powershell
Undo-RemoteWorkerUpdate
```

The service automatically:
- Backs up the current script before updating
- Restarts itself after the update
- Allows rollback to the previous version

## Job Pool (Multi-Worker Distribution)

The job pool system uses PostgreSQL for distributing work across multiple machines.
Jobs are placed in a shared queue that any available worker can claim atomically.

### When to Use Job Pool vs File-Based

| Use File-Based | Use Job Pool |
|----------------|--------------|
| Quick interactive commands | Batch processing (OCR, extraction) |
| Targeting a specific worker | Load-balanced across workers |
| Real-time responses needed | Can tolerate queue delay |
| Simple status checks | Large parallelizable workloads |

### Test Connection
```powershell
Test-JobPoolConnection
```

### Submit Jobs to Pool
```powershell
# Submit a PowerShell job
Submit-PooledJob -JobType "general" -Payload @{
    action = "powershell"
    command = "Get-Process | Sort CPU -Desc | Select -First 10"
}

# Submit with priority (higher = more urgent)
Submit-PooledJob -JobType "general" -Payload @{
    action = "python"
    script = "C:\scripts\process_batch.py"
    args = @("--input", "data.csv")
} -Priority 10

# Quick submit and wait
Invoke-PooledPowerShell "Get-ChildItem C:\Temp"
```

### Monitor Jobs
```powershell
# Get status of a specific job
Get-PooledJobStatus -JobId 123

# Wait for job completion
$result = Wait-PooledJob -JobId 123

# View progress by job type
Get-JobPoolProgress | Format-Table

# See active workers
Get-ActivePoolWorkers

# View recent errors
Get-RecentPoolErrors -Limit 10
```

### Retry Failed Jobs
```powershell
# Reset all failed jobs to pending
Reset-FailedPoolJobs

# Reset only specific job type
Reset-FailedPoolJobs -JobType "ocr"
```

### Starting the Python Worker

On each worker machine, run:
```bash
cd D:\Personal\Epstein\epstein_extraction
python services/pooled_job_worker.py
```

The worker will automatically:
- Check for updates from the git repository
- Detect machine capabilities (CPU cores, memory)
- Set optimal concurrency based on resources

### Worker Options

```bash
# Auto-detect everything (recommended)
python services/pooled_job_worker.py

# Process specific job types
python services/pooled_job_worker.py --job-types ocr,entity

# Override auto-detected concurrency
python services/pooled_job_worker.py --max-concurrent 5

# Show machine capabilities
python services/pooled_job_worker.py --show-capabilities

# Check for updates
python services/pooled_job_worker.py --check-update

# Skip auto-update check
python services/pooled_job_worker.py --no-update
```

Options:
- `--job-types general,ocr`: Only process specific job types
- `--max-concurrent N`: Override auto-detected concurrency
- `--poll-interval 1.0`: Poll every 1 second (default: 2.0)
- `--stale-timeout 30`: Reclaim stale jobs after 30 minutes
- `--no-update`: Skip version check on startup
- `--check-update`: Check for updates and prompt to apply
- `--show-capabilities`: Display machine capabilities and exit

### Auto-Update Feature

The worker checks its version against the git repository on startup:
- If an update is available, it pulls changes and restarts automatically
- Use `--no-update` to skip this check
- Use `--check-update` for interactive update control

### Capability Detection

The worker auto-detects machine resources:
- **CPU cores**: Physical cores for optimal parallelism
- **Memory**: Available RAM for memory-intensive jobs
- **Recommended concurrency** based on job type:
  - `general`: ~500MB per job
  - `ocr`: ~1GB per job
  - `vision`: ~2GB per job
  - `entity`: ~300MB per job

## Troubleshooting

### Cannot connect to share
1. Verify Tailscale is running: `tailscale status`
2. Test connectivity: `Test-NetConnection 100.75.137.22 -Port 445`

### Command times out
- Increase timeout: `-Timeout 300` (5 minutes)
- Use `-Wait:$false` for long-running processes

### Check service status on remote
```powershell
Invoke-RemotePowerShell "Get-ScheduledTask -TaskName 'RemoteWorkerService' | Select TaskName, State"
```

## Files

- Client module: `D:\Personal\Epstein\remote-worker\scripts\RemoteWorkerClient.ps1`
- Service script: `remote-worker\scripts\RemoteWorkerService.ps1`
- Setup script: `remote-worker\scripts\Setup-RemoteWorker.ps1`
- Documentation: `remote-worker\README.md`
