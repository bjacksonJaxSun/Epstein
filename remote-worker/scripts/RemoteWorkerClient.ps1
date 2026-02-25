#Requires -Version 5.1
<#
.SYNOPSIS
    Remote Worker Client - Send commands to remote worker machines.

.DESCRIPTION
    This module provides functions to send commands to remote worker machines
    via shared folders over Tailscale. It handles command creation, result
    retrieval, and provides convenient wrappers for common operations.

.NOTES
    Author: Remote Worker System
    Version: 1.0.0
#>

# Default configuration - override by setting $RemoteWorkerConfig before importing
if (-not $script:RemoteWorkerConfig) {
    $script:RemoteWorkerConfig = @{
        Workers = @{
            "bobbyhomeep" = @{
                TailscaleIP = "100.75.137.22"
                CommandsPath = "\\100.75.137.22\RemoteWorker\commands"
                ResultsPath = "\\100.75.137.22\RemoteWorker\results"
            }
        }
        DefaultWorker = "bobbyhomeep"
        ResultTimeoutSeconds = 300
        PollIntervalMs = 500
    }
}

function Get-WorkerConfig {
    param([string]$WorkerName)

    if (-not $WorkerName) {
        $WorkerName = $script:RemoteWorkerConfig.DefaultWorker
    }

    $worker = $script:RemoteWorkerConfig.Workers[$WorkerName]
    if (-not $worker) {
        throw "Worker '$WorkerName' not found in configuration. Available workers: $($script:RemoteWorkerConfig.Workers.Keys -join ', ')"
    }

    return $worker
}

function Send-RemoteCommand {
    <#
    .SYNOPSIS
        Sends a command to a remote worker machine.

    .PARAMETER Action
        The type of action: powershell, cmd, process-start, process-stop, status, file-transfer

    .PARAMETER Command
        The command or executable to run

    .PARAMETER Worker
        Target worker name (default: bobbyhomeep)

    .PARAMETER Wait
        Wait for the result (default: $true)

    .PARAMETER Timeout
        Command timeout in seconds

    .EXAMPLE
        Send-RemoteCommand -Action powershell -Command "Get-Process"

    .EXAMPLE
        Send-RemoteCommand -Action process-start -Command "notepad.exe" -Wait:$false
    #>

    param(
        [Parameter(Mandatory)]
        [ValidateSet("powershell", "cmd", "process-start", "process-stop", "status", "file-transfer")]
        [string]$Action,

        [Parameter(Mandatory=$false)]
        [AllowEmptyString()]
        [string]$Command = "",

        [string]$Worker,

        [switch]$Wait = $true,

        [int]$Timeout = 60,

        [string]$Arguments,

        [string]$WorkingDirectory,

        [hashtable]$ExtraParams
    )

    $config = Get-WorkerConfig -WorkerName $Worker

    # Generate unique job ID
    $jobId = "job-$(Get-Date -Format 'yyyyMMdd-HHmmss')-$([guid]::NewGuid().ToString().Substring(0,8))"

    # Build command object
    $commandObj = @{
        id = $jobId
        action = $Action
        command = $Command
        timeout = $Timeout
        timestamp = (Get-Date).ToString("o")
        source = $env:COMPUTERNAME
    }

    if ($Arguments) { $commandObj.arguments = $Arguments }
    if ($WorkingDirectory) { $commandObj.workingDirectory = $WorkingDirectory }
    if ($ExtraParams) {
        foreach ($key in $ExtraParams.Keys) {
            $commandObj[$key] = $ExtraParams[$key]
        }
    }

    # Write command file
    $commandFile = Join-Path $config.CommandsPath "$jobId.json"

    try {
        $commandObj | ConvertTo-Json -Depth 10 | Set-Content -Path $commandFile -Encoding UTF8
        Write-Host "Command sent: $jobId" -ForegroundColor Cyan
    } catch {
        throw "Failed to send command. Is the share accessible? Error: $($_.Exception.Message)"
    }

    if (-not $Wait) {
        return [PSCustomObject]@{
            JobId = $jobId
            Status = "submitted"
            Worker = $Worker
        }
    }

    # Wait for result
    return Wait-RemoteResult -JobId $jobId -Worker $Worker -Timeout $script:RemoteWorkerConfig.ResultTimeoutSeconds
}

function Wait-RemoteResult {
    <#
    .SYNOPSIS
        Waits for and retrieves the result of a remote command.
    #>

    param(
        [Parameter(Mandatory)]
        [string]$JobId,

        [string]$Worker,

        [int]$Timeout = 300
    )

    $config = Get-WorkerConfig -WorkerName $Worker
    $resultFile = Join-Path $config.ResultsPath "$JobId.json"

    $startTime = Get-Date
    $pollInterval = $script:RemoteWorkerConfig.PollIntervalMs

    Write-Host "Waiting for result..." -ForegroundColor Gray -NoNewline

    while ((Get-Date) -lt $startTime.AddSeconds($Timeout)) {
        if (Test-Path $resultFile) {
            Start-Sleep -Milliseconds 100  # Brief delay to ensure file is fully written
            $result = Get-Content $resultFile -Raw | ConvertFrom-Json
            Write-Host " Done!" -ForegroundColor Green
            return $result
        }

        Write-Host "." -NoNewline -ForegroundColor Gray
        Start-Sleep -Milliseconds $pollInterval
    }

    Write-Host " Timeout!" -ForegroundColor Red
    return [PSCustomObject]@{
        id = $JobId
        status = "timeout"
        error = "No result received within $Timeout seconds"
    }
}

function Get-RemoteResult {
    <#
    .SYNOPSIS
        Retrieves the result of a previously submitted command.
    #>

    param(
        [Parameter(Mandatory)]
        [string]$JobId,

        [string]$Worker
    )

    $config = Get-WorkerConfig -WorkerName $Worker
    $resultFile = Join-Path $config.ResultsPath "$JobId.json"

    if (Test-Path $resultFile) {
        return Get-Content $resultFile -Raw | ConvertFrom-Json
    }

    return $null
}

# Convenience functions

function Invoke-RemotePowerShell {
    <#
    .SYNOPSIS
        Executes a PowerShell command on a remote worker.

    .EXAMPLE
        Invoke-RemotePowerShell "Get-Process | Sort-Object CPU -Descending | Select-Object -First 10"

    .EXAMPLE
        Invoke-RemotePowerShell "Get-ChildItem C:\Temp" -Worker "bobbyhomeep"
    #>

    param(
        [Parameter(Mandatory, Position = 0)]
        [string]$Command,

        [string]$Worker,

        [int]$Timeout = 60
    )

    Send-RemoteCommand -Action powershell -Command $Command -Worker $Worker -Timeout $Timeout
}

function Invoke-RemoteCmd {
    <#
    .SYNOPSIS
        Executes a CMD command on a remote worker.

    .EXAMPLE
        Invoke-RemoteCmd "dir C:\Temp"
    #>

    param(
        [Parameter(Mandatory, Position = 0)]
        [string]$Command,

        [string]$Worker,

        [int]$Timeout = 60
    )

    Send-RemoteCommand -Action cmd -Command $Command -Worker $Worker -Timeout $Timeout
}

function Start-RemoteProcess {
    <#
    .SYNOPSIS
        Starts a process on a remote worker.

    .EXAMPLE
        Start-RemoteProcess "notepad.exe"

    .EXAMPLE
        Start-RemoteProcess "python.exe" -Arguments "C:\scripts\myscript.py"
    #>

    param(
        [Parameter(Mandatory, Position = 0)]
        [string]$Executable,

        [string]$Arguments,

        [string]$WorkingDirectory,

        [string]$Worker,

        [switch]$Track
    )

    $params = @{
        Action = "process-start"
        Command = $Executable
        Worker = $Worker
    }

    if ($Arguments) { $params.Arguments = $Arguments }
    if ($WorkingDirectory) { $params.WorkingDirectory = $WorkingDirectory }
    if ($Track) { $params.ExtraParams = @{ trackProcess = $true } }

    Send-RemoteCommand @params
}

function Stop-RemoteProcess {
    <#
    .SYNOPSIS
        Stops a process on a remote worker.

    .EXAMPLE
        Stop-RemoteProcess -ProcessName "notepad"

    .EXAMPLE
        Stop-RemoteProcess -ProcessId 1234
    #>

    param(
        [string]$ProcessName,

        [int]$ProcessId,

        [string]$Worker
    )

    $extraParams = @{}
    if ($ProcessName) { $extraParams.processName = $ProcessName }
    if ($ProcessId) { $extraParams.processId = $ProcessId }

    Send-RemoteCommand -Action process-stop -Command "" -Worker $Worker -ExtraParams $extraParams
}

function Get-RemoteStatus {
    <#
    .SYNOPSIS
        Gets the current status of a remote worker (CPU, memory, uptime, etc.)

    .EXAMPLE
        Get-RemoteStatus

    .EXAMPLE
        Get-RemoteStatus -Worker "bobbyhomeep"
    #>

    param([string]$Worker)

    $result = Send-RemoteCommand -Action status -Command "" -Worker $Worker
    if ($result.output) {
        return $result.output | ConvertFrom-Json
    }
    return $result
}

function Send-FileToWorker {
    <#
    .SYNOPSIS
        Uploads a file to a remote worker.

    .EXAMPLE
        Send-FileToWorker -LocalPath "C:\scripts\myscript.py" -RemotePath "C:\Temp\myscript.py"
    #>

    param(
        [Parameter(Mandatory)]
        [string]$LocalPath,

        [Parameter(Mandatory)]
        [string]$RemotePath,

        [string]$Worker
    )

    if (-not (Test-Path $LocalPath)) {
        throw "Local file not found: $LocalPath"
    }

    $bytes = [IO.File]::ReadAllBytes($LocalPath)
    $content = [Convert]::ToBase64String($bytes)

    $extraParams = @{
        direction = "upload"
        content = $content
        destination = $RemotePath
    }

    Send-RemoteCommand -Action file-transfer -Command "" -Worker $Worker -ExtraParams $extraParams
}

function Get-FileFromWorker {
    <#
    .SYNOPSIS
        Downloads a file from a remote worker.

    .EXAMPLE
        Get-FileFromWorker -RemotePath "C:\Temp\results.csv" -LocalPath "C:\Downloads\results.csv"
    #>

    param(
        [Parameter(Mandatory)]
        [string]$RemotePath,

        [Parameter(Mandatory)]
        [string]$LocalPath,

        [string]$Worker
    )

    $extraParams = @{
        direction = "download"
        source = $RemotePath
    }

    $result = Send-RemoteCommand -Action file-transfer -Command "" -Worker $Worker -ExtraParams $extraParams

    if ($result.status -eq "completed" -and $result.output) {
        $bytes = [Convert]::FromBase64String($result.output)
        [IO.File]::WriteAllBytes($LocalPath, $bytes)
        Write-Host "File downloaded to: $LocalPath" -ForegroundColor Green
    } else {
        throw "Failed to download file: $($result.error)"
    }
}

# Service Management Functions

function Update-RemoteWorkerService {
    <#
    .SYNOPSIS
        Updates the Remote Worker service script on a remote worker.

    .DESCRIPTION
        Pushes a new version of RemoteWorkerService.ps1 to the remote worker.
        The worker will backup the current script and restart automatically.

    .PARAMETER ScriptPath
        Path to the new service script (default: same directory as client)

    .PARAMETER Worker
        Target worker name

    .EXAMPLE
        Update-RemoteWorkerService

    .EXAMPLE
        Update-RemoteWorkerService -ScriptPath "C:\scripts\RemoteWorkerService.ps1" -Worker "bobbyhomeep"
    #>

    param(
        [string]$ScriptPath,

        [string]$Worker
    )

    # Default to the service script in the same directory as this client
    if (-not $ScriptPath) {
        $ScriptPath = Join-Path $PSScriptRoot "RemoteWorkerService.ps1"
    }

    if (-not (Test-Path $ScriptPath)) {
        throw "Service script not found: $ScriptPath"
    }

    Write-Host "Reading service script from: $ScriptPath" -ForegroundColor Cyan
    $scriptContent = Get-Content $ScriptPath -Raw
    $base64Content = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($scriptContent))

    Write-Host "Pushing update to remote worker..." -ForegroundColor Yellow

    $extraParams = @{
        content = $base64Content
    }

    $result = Send-RemoteCommand -Action "service-update" -Command "" -Worker $Worker -ExtraParams $extraParams -Timeout 60

    if ($result.status -eq "completed") {
        Write-Host "Update successful! Worker will restart in a few seconds." -ForegroundColor Green
        Write-Host "Use Get-RemoteWorkerVersion to verify the update after ~10 seconds." -ForegroundColor Gray
    } else {
        Write-Host "Update failed: $($result.error)" -ForegroundColor Red
    }

    return $result
}

function Get-RemoteWorkerVersion {
    <#
    .SYNOPSIS
        Gets the current version information of the remote worker service.

    .DESCRIPTION
        Returns the script hash and last modified time of the service script.

    .EXAMPLE
        Get-RemoteWorkerVersion

    .EXAMPLE
        Get-RemoteWorkerVersion -Worker "bobbyhomeep"
    #>

    param([string]$Worker)

    $result = Send-RemoteCommand -Action "service-version" -Command "" -Worker $Worker

    if ($result.status -eq "completed" -and $result.output) {
        return $result.output | ConvertFrom-Json
    }

    return $result
}

function Undo-RemoteWorkerUpdate {
    <#
    .SYNOPSIS
        Rolls back the remote worker service to the previous version.

    .DESCRIPTION
        Restores the backup script created during the last update and restarts the service.

    .EXAMPLE
        Undo-RemoteWorkerUpdate

    .EXAMPLE
        Undo-RemoteWorkerUpdate -Worker "bobbyhomeep"
    #>

    param([string]$Worker)

    Write-Host "Rolling back to previous version..." -ForegroundColor Yellow

    $result = Send-RemoteCommand -Action "service-rollback" -Command "" -Worker $Worker -Timeout 60

    if ($result.status -eq "completed") {
        Write-Host "Rollback successful! Worker will restart in a few seconds." -ForegroundColor Green
    } else {
        Write-Host "Rollback failed: $($result.error)" -ForegroundColor Red
    }

    return $result
}

# ============================================
# POOLED JOB FUNCTIONS (Database-based)
# Multi-machine job pool using PostgreSQL
# ============================================

# Job Pool Configuration
if (-not $script:JobPoolConfig) {
    $script:JobPoolConfig = @{
        Host = "100.75.137.22"  # BobbyHomeEP via Tailscale
        Database = "epstein_documents"
        Username = "epstein_user"
        Password = "epstein_secure_pw_2024"
        PsqlPath = $null  # Auto-detect or set manually
    }
}

function Get-PsqlPath {
    <#
    .SYNOPSIS
        Finds the psql executable path.
    #>

    if ($script:JobPoolConfig.PsqlPath -and (Test-Path $script:JobPoolConfig.PsqlPath)) {
        return $script:JobPoolConfig.PsqlPath
    }

    # Try common locations
    $possiblePaths = @(
        "C:\Program Files\PostgreSQL\16\bin\psql.exe",
        "C:\Program Files\PostgreSQL\15\bin\psql.exe",
        "C:\Program Files\PostgreSQL\14\bin\psql.exe",
        "C:\Program Files\PostgreSQL\13\bin\psql.exe",
        (Get-Command psql -ErrorAction SilentlyContinue).Source
    )

    foreach ($path in $possiblePaths) {
        if ($path -and (Test-Path $path)) {
            $script:JobPoolConfig.PsqlPath = $path
            return $path
        }
    }

    throw "psql not found. Install PostgreSQL client tools or set `$script:JobPoolConfig.PsqlPath"
}

function Invoke-PoolQuery {
    <#
    .SYNOPSIS
        Executes a query against the job pool database.
    #>

    param(
        [Parameter(Mandatory)]
        [string]$Query,

        [switch]$Scalar,
        [switch]$NoOutput
    )

    $psql = Get-PsqlPath
    $env:PGPASSWORD = $script:JobPoolConfig.Password

    $args = @(
        "-h", $script:JobPoolConfig.Host,
        "-U", $script:JobPoolConfig.Username,
        "-d", $script:JobPoolConfig.Database,
        "-t", "-A"  # Tuples only, unaligned output
    )

    if (-not $NoOutput) {
        $args += "-c", $Query
    }

    try {
        if ($NoOutput) {
            $result = $Query | & $psql @args 2>&1
        } else {
            $result = & $psql @args 2>&1
        }

        if ($LASTEXITCODE -ne 0) {
            throw "Query failed: $result"
        }

        if ($Scalar) {
            return ($result | Select-Object -First 1).Trim()
        }

        return $result
    } finally {
        Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
    }
}

function Test-JobPoolConnection {
    <#
    .SYNOPSIS
        Tests the connection to the job pool database.

    .EXAMPLE
        Test-JobPoolConnection
    #>

    try {
        $result = Invoke-PoolQuery -Query "SELECT 1" -Scalar
        if ($result -eq "1") {
            Write-Host "Job pool connection successful!" -ForegroundColor Green
            return $true
        }
    } catch {
        Write-Host "Job pool connection failed: $_" -ForegroundColor Red
        return $false
    }
    return $false
}

function Submit-PooledJob {
    <#
    .SYNOPSIS
        Submits a job to the database-based job pool.

    .DESCRIPTION
        Jobs are placed in a shared queue that any worker can claim.
        This enables multi-machine job distribution.

    .PARAMETER JobType
        Type of job: 'general', 'ocr', 'entity', 'vision', etc.

    .PARAMETER Payload
        Job payload as a hashtable. For 'general' jobs, include:
        - action: 'powershell', 'python', 'shell', or 'executable'
        - command: The command to run (for powershell/shell)
        - script: The script path (for python)
        - args: Optional arguments array

    .PARAMETER Priority
        Job priority (higher = more urgent). Default: 0

    .PARAMETER TimeoutSeconds
        Job timeout in seconds. Default: 300

    .EXAMPLE
        Submit-PooledJob -JobType "general" -Payload @{action="powershell"; command="Get-Process"}

    .EXAMPLE
        Submit-PooledJob -JobType "ocr" -Payload @{document_id=123; page=1} -Priority 10
    #>

    param(
        [Parameter(Mandatory)]
        [string]$JobType,

        [Parameter(Mandatory)]
        [hashtable]$Payload,

        [int]$Priority = 0,
        [int]$TimeoutSeconds = 300
    )

    $payloadJson = ($Payload | ConvertTo-Json -Compress -Depth 10) -replace "'", "''"

    $query = "SELECT submit_job('$JobType', '$payloadJson'::jsonb, $Priority, $TimeoutSeconds, '$env:COMPUTERNAME')"

    try {
        $jobId = Invoke-PoolQuery -Query $query -Scalar
        Write-Host "Submitted job $jobId ($JobType)" -ForegroundColor Cyan
        return [int]$jobId
    } catch {
        Write-Host "Failed to submit job: $_" -ForegroundColor Red
        throw
    }
}

function Get-PooledJobStatus {
    <#
    .SYNOPSIS
        Gets the status of a pooled job.

    .EXAMPLE
        Get-PooledJobStatus -JobId 123
    #>

    param(
        [Parameter(Mandatory)]
        [int]$JobId
    )

    $query = @"
SELECT row_to_json(t) FROM (
    SELECT job_id, job_type, status, exit_code, error_message,
           result::text, LEFT(output_text, 2000) as output_preview,
           created_at, started_at, completed_at, claimed_by, retry_count
    FROM job_pool WHERE job_id = $JobId
) t
"@

    $result = Invoke-PoolQuery -Query $query -Scalar

    if ($result) {
        return $result | ConvertFrom-Json
    }

    return $null
}

function Wait-PooledJob {
    <#
    .SYNOPSIS
        Waits for a pooled job to complete.

    .EXAMPLE
        $result = Wait-PooledJob -JobId 123

    .EXAMPLE
        $result = Wait-PooledJob -JobId 123 -TimeoutSeconds 600
    #>

    param(
        [Parameter(Mandatory)]
        [int]$JobId,

        [int]$TimeoutSeconds = 3600,
        [int]$PollIntervalMs = 2000
    )

    $start = Get-Date
    Write-Host "Waiting for job $JobId..." -ForegroundColor Gray -NoNewline

    while ((Get-Date) -lt $start.AddSeconds($TimeoutSeconds)) {
        $status = Get-PooledJobStatus -JobId $JobId

        if ($status.status -in @('completed', 'failed', 'skipped')) {
            Write-Host " Done!" -ForegroundColor Green
            return $status
        }

        Write-Host "." -NoNewline -ForegroundColor Gray
        Start-Sleep -Milliseconds $PollIntervalMs
    }

    Write-Host " Timeout!" -ForegroundColor Red
    throw "Timeout waiting for job $JobId"
}

function Get-JobPoolProgress {
    <#
    .SYNOPSIS
        Gets the progress of all jobs in the pool.

    .EXAMPLE
        Get-JobPoolProgress
    #>

    $query = "SELECT row_to_json(t) FROM job_pool_progress t"

    $results = Invoke-PoolQuery -Query $query

    $progress = @()
    foreach ($row in $results) {
        if ($row.Trim()) {
            $progress += ($row | ConvertFrom-Json)
        }
    }

    return $progress
}

function Get-ActivePoolWorkers {
    <#
    .SYNOPSIS
        Gets information about active workers in the pool.

    .EXAMPLE
        Get-ActivePoolWorkers
    #>

    $query = "SELECT row_to_json(t) FROM active_pool_workers t"

    $results = Invoke-PoolQuery -Query $query

    $workers = @()
    foreach ($row in $results) {
        if ($row.Trim()) {
            $workers += ($row | ConvertFrom-Json)
        }
    }

    return $workers
}

function Get-RecentPoolErrors {
    <#
    .SYNOPSIS
        Gets recent errors from the job pool.

    .PARAMETER Limit
        Maximum number of errors to return. Default: 20

    .EXAMPLE
        Get-RecentPoolErrors
    #>

    param([int]$Limit = 20)

    $query = "SELECT row_to_json(t) FROM (SELECT * FROM recent_pool_errors LIMIT $Limit) t"

    $results = Invoke-PoolQuery -Query $query

    $errors = @()
    foreach ($row in $results) {
        if ($row.Trim()) {
            $errors += ($row | ConvertFrom-Json)
        }
    }

    return $errors
}

function Reset-FailedPoolJobs {
    <#
    .SYNOPSIS
        Resets failed jobs to pending for retry.

    .PARAMETER JobType
        Optional job type filter

    .EXAMPLE
        Reset-FailedPoolJobs

    .EXAMPLE
        Reset-FailedPoolJobs -JobType "ocr"
    #>

    param([string]$JobType)

    $typeParam = if ($JobType) { "'$JobType'" } else { "NULL" }
    $query = "SELECT reset_failed_jobs($typeParam)"

    $count = Invoke-PoolQuery -Query $query -Scalar
    Write-Host "Reset $count failed jobs to pending" -ForegroundColor Green
    return [int]$count
}

function Invoke-PooledPowerShell {
    <#
    .SYNOPSIS
        Submits a PowerShell command to the job pool and waits for result.

    .DESCRIPTION
        Convenience function that submits a general job with a PowerShell action
        and waits for the result.

    .EXAMPLE
        Invoke-PooledPowerShell "Get-Process | Select -First 5"

    .EXAMPLE
        Invoke-PooledPowerShell "Get-ChildItem C:\Temp" -Priority 10 -TimeoutSeconds 120
    #>

    param(
        [Parameter(Mandatory, Position = 0)]
        [string]$Command,

        [int]$Priority = 0,
        [int]$TimeoutSeconds = 300
    )

    $jobId = Submit-PooledJob -JobType "general" -Payload @{
        action = "powershell"
        command = $Command
        timeout = $TimeoutSeconds
    } -Priority $Priority -TimeoutSeconds $TimeoutSeconds

    return Wait-PooledJob -JobId $jobId -TimeoutSeconds ($TimeoutSeconds + 60)
}

function Show-RemoteWorkerHelp {
    Write-Host @"

Remote Worker Client - Command Reference
=========================================

BASIC COMMANDS (File-based, point-to-point):
  Invoke-RemotePowerShell "command"    Execute PowerShell on specific worker
  Invoke-RemoteCmd "command"           Execute CMD on specific worker
  Get-RemoteStatus                     Get worker CPU, memory, and job status

POOLED JOBS (Database-based, multi-worker):
  Test-JobPoolConnection               Test database connection
  Submit-PooledJob -JobType X -Payload Y   Submit job to pool
  Get-PooledJobStatus -JobId X         Get job status
  Wait-PooledJob -JobId X              Wait for job completion
  Invoke-PooledPowerShell "command"    Submit and wait for PowerShell job
  Get-JobPoolProgress                  View progress by job type
  Get-ActivePoolWorkers                See which workers are active
  Get-RecentPoolErrors                 View recent failures
  Reset-FailedPoolJobs                 Reset failed jobs for retry

PROCESS MANAGEMENT:
  Start-RemoteProcess "app.exe"        Start a process
  Stop-RemoteProcess -ProcessName X    Stop a process by name
  Stop-RemoteProcess -ProcessId 123    Stop a process by ID

FILE TRANSFER:
  Send-FileToWorker -LocalPath X -RemotePath Y    Upload file
  Get-FileFromWorker -RemotePath X -LocalPath Y   Download file

SERVICE MANAGEMENT:
  Update-RemoteWorkerService           Push new service script to worker
  Get-RemoteWorkerVersion              Get service script hash and version
  Undo-RemoteWorkerUpdate              Rollback to previous version

LOW-LEVEL:
  Send-RemoteCommand -Action X -Command Y   Send any command
  Wait-RemoteResult -JobId X                Wait for job result
  Get-RemoteResult -JobId X                 Get existing result

EXAMPLES:
  # File-based (single worker)
  Invoke-RemotePowerShell "Get-Process | Select -First 5"
  Start-RemoteProcess "python.exe" -Arguments "C:\script.py"

  # Pooled jobs (any available worker)
  Submit-PooledJob -JobType "general" -Payload @{action="powershell"; command="Get-Process"}
  Invoke-PooledPowerShell "Get-ChildItem C:\Temp"
  Get-JobPoolProgress | Format-Table

"@ -ForegroundColor Cyan
}

# Export functions when loaded as a module
if ($MyInvocation.MyCommand.ScriptBlock.Module) {
    Export-ModuleMember -Function @(
        # File-based commands (point-to-point)
        'Send-RemoteCommand',
        'Wait-RemoteResult',
        'Get-RemoteResult',
        'Invoke-RemotePowerShell',
        'Invoke-RemoteCmd',
        'Start-RemoteProcess',
        'Stop-RemoteProcess',
        'Get-RemoteStatus',
        'Send-FileToWorker',
        'Get-FileFromWorker',
        'Update-RemoteWorkerService',
        'Get-RemoteWorkerVersion',
        'Undo-RemoteWorkerUpdate',
        # Pooled jobs (database-based)
        'Test-JobPoolConnection',
        'Submit-PooledJob',
        'Get-PooledJobStatus',
        'Wait-PooledJob',
        'Get-JobPoolProgress',
        'Get-ActivePoolWorkers',
        'Get-RecentPoolErrors',
        'Reset-FailedPoolJobs',
        'Invoke-PooledPowerShell',
        # Help
        'Show-RemoteWorkerHelp'
    )
}
