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

        [Parameter(Mandatory)]
        [string]$Command,

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

function Show-RemoteWorkerHelp {
    Write-Host @"

Remote Worker Client - Command Reference
=========================================

BASIC COMMANDS:
  Invoke-RemotePowerShell "command"    Execute PowerShell on remote worker
  Invoke-RemoteCmd "command"           Execute CMD on remote worker
  Get-RemoteStatus                     Get worker CPU, memory, and job status

PROCESS MANAGEMENT:
  Start-RemoteProcess "app.exe"        Start a process
  Stop-RemoteProcess -ProcessName X    Stop a process by name
  Stop-RemoteProcess -ProcessId 123    Stop a process by ID

FILE TRANSFER:
  Send-FileToWorker -LocalPath X -RemotePath Y    Upload file
  Get-FileFromWorker -RemotePath X -LocalPath Y   Download file

LOW-LEVEL:
  Send-RemoteCommand -Action X -Command Y   Send any command
  Wait-RemoteResult -JobId X                Wait for job result
  Get-RemoteResult -JobId X                 Get existing result

EXAMPLES:
  Invoke-RemotePowerShell "Get-Process | Select -First 5"
  Start-RemoteProcess "python.exe" -Arguments "C:\script.py"
  Get-RemoteStatus | Format-List

"@ -ForegroundColor Cyan
}

# Export functions
Export-ModuleMember -Function @(
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
    'Show-RemoteWorkerHelp'
)
