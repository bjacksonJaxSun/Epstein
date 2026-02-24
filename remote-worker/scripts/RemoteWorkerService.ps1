#Requires -Version 5.1
<#
.SYNOPSIS
    Remote Worker Service - Monitors a folder for command files and executes them.

.DESCRIPTION
    This script watches a designated folder for JSON command files, executes the
    commands, and writes results back to a results folder. Designed to run as a
    Windows service for remote workload distribution via Tailscale.

.NOTES
    Author: Remote Worker System
    Version: 1.0.0
#>

param(
    [string]$ConfigPath = "$PSScriptRoot\..\config.json"
)

# Global state
$script:RunningJobs = @{}
$script:Config = $null
$script:Watcher = $null
$script:Running = $true

function Write-Log {
    param(
        [string]$Message,
        [ValidateSet('INFO', 'WARN', 'ERROR', 'DEBUG')]
        [string]$Level = 'INFO'
    )

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"

    # Console output
    switch ($Level) {
        'ERROR' { Write-Host $logEntry -ForegroundColor Red }
        'WARN'  { Write-Host $logEntry -ForegroundColor Yellow }
        'DEBUG' { Write-Host $logEntry -ForegroundColor Gray }
        default { Write-Host $logEntry }
    }

    # File logging
    if ($script:Config.enableLogging -and $script:Config.logsFolder) {
        $logFile = Join-Path $script:Config.logsFolder "worker-$(Get-Date -Format 'yyyy-MM-dd').log"
        Add-Content -Path $logFile -Value $logEntry -ErrorAction SilentlyContinue
    }
}

function Initialize-Config {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        throw "Configuration file not found: $Path"
    }

    $script:Config = Get-Content $Path -Raw | ConvertFrom-Json

    # Ensure folders exist
    @($script:Config.watchFolder, $script:Config.resultsFolder, $script:Config.logsFolder) | ForEach-Object {
        if (-not (Test-Path $_)) {
            New-Item -Path $_ -ItemType Directory -Force | Out-Null
            Write-Log "Created directory: $_"
        }
    }

    # Create subfolders for organization
    $processingFolder = Join-Path $script:Config.watchFolder "processing"
    $completedFolder = Join-Path $script:Config.watchFolder "completed"
    $failedFolder = Join-Path $script:Config.watchFolder "failed"

    @($processingFolder, $completedFolder, $failedFolder) | ForEach-Object {
        if (-not (Test-Path $_)) {
            New-Item -Path $_ -ItemType Directory -Force | Out-Null
        }
    }

    Write-Log "Configuration loaded from $Path"
    Write-Log "Worker Name: $($script:Config.workerName)"
    Write-Log "Watching: $($script:Config.watchFolder)"
}

function Test-CommandAllowed {
    param([string]$Command)

    # Check blocked commands
    foreach ($blocked in $script:Config.blockedCommands) {
        if ($Command -match [regex]::Escape($blocked)) {
            return $false
        }
    }

    # If allowedCommands is empty, allow all (except blocked)
    if ($script:Config.allowedCommands.Count -eq 0) {
        return $true
    }

    # Check allowed commands
    foreach ($allowed in $script:Config.allowedCommands) {
        if ($Command -match [regex]::Escape($allowed)) {
            return $true
        }
    }

    return $false
}

function Invoke-CommandJob {
    param(
        [PSCustomObject]$CommandData,
        [string]$CommandFile
    )

    $jobId = $CommandData.id
    $startTime = Get-Date

    $result = [PSCustomObject]@{
        id = $jobId
        workerName = $script:Config.workerName
        status = "running"
        startTime = $startTime.ToString("o")
        endTime = $null
        durationMs = $null
        exitCode = $null
        output = $null
        error = $null
        command = $CommandData.command
        action = $CommandData.action
    }

    try {
        Write-Log "Executing job $jobId : $($CommandData.action)"

        # Validate command
        if (-not (Test-CommandAllowed -Command $CommandData.command)) {
            throw "Command not allowed by security policy"
        }

        $timeout = if ($CommandData.timeout) { $CommandData.timeout } else { $script:Config.commandTimeoutSeconds }

        switch ($CommandData.action.ToLower()) {
            "powershell" {
                $scriptBlock = [ScriptBlock]::Create($CommandData.command)
                $job = Start-Job -ScriptBlock $scriptBlock

                $completed = $job | Wait-Job -Timeout $timeout

                if ($job.State -eq 'Running') {
                    $job | Stop-Job
                    $job | Remove-Job -Force
                    throw "Command timed out after $timeout seconds"
                }

                $output = $job | Receive-Job
                $result.output = $output | Out-String
                $result.exitCode = 0
                $job | Remove-Job -Force
            }

            "process-start" {
                $processParams = @{
                    FilePath = $CommandData.command
                    PassThru = $true
                }

                if ($CommandData.arguments) {
                    $processParams.ArgumentList = $CommandData.arguments
                }

                if ($CommandData.workingDirectory) {
                    $processParams.WorkingDirectory = $CommandData.workingDirectory
                }

                $process = Start-Process @processParams
                $result.output = "Process started with PID: $($process.Id)"
                $result.exitCode = 0

                # Track the process if we need to manage it later
                if ($CommandData.trackProcess) {
                    $script:RunningJobs[$jobId] = @{
                        ProcessId = $process.Id
                        StartTime = $startTime
                    }
                }
            }

            "process-stop" {
                $process = $null

                if ($CommandData.processId) {
                    $process = Get-Process -Id $CommandData.processId -ErrorAction SilentlyContinue
                } elseif ($CommandData.processName) {
                    $process = Get-Process -Name $CommandData.processName -ErrorAction SilentlyContinue
                }

                if ($process) {
                    $process | Stop-Process -Force
                    $result.output = "Process(es) stopped successfully"
                    $result.exitCode = 0
                } else {
                    throw "Process not found"
                }
            }

            "cmd" {
                $processInfo = New-Object System.Diagnostics.ProcessStartInfo
                $processInfo.FileName = "cmd.exe"
                $processInfo.Arguments = "/c $($CommandData.command)"
                $processInfo.RedirectStandardOutput = $true
                $processInfo.RedirectStandardError = $true
                $processInfo.UseShellExecute = $false
                $processInfo.CreateNoWindow = $true

                $process = New-Object System.Diagnostics.Process
                $process.StartInfo = $processInfo
                $process.Start() | Out-Null

                $stdout = $process.StandardOutput.ReadToEnd()
                $stderr = $process.StandardError.ReadToEnd()

                $completed = $process.WaitForExit($timeout * 1000)

                if (-not $completed) {
                    $process.Kill()
                    throw "Command timed out after $timeout seconds"
                }

                $result.output = $stdout
                if ($stderr) { $result.error = $stderr }
                $result.exitCode = $process.ExitCode
            }

            "status" {
                # Return system status
                $cpuLoad = (Get-CimInstance -ClassName Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
                $memory = Get-CimInstance -ClassName Win32_OperatingSystem
                $memoryUsedPct = [math]::Round((($memory.TotalVisibleMemorySize - $memory.FreePhysicalMemory) / $memory.TotalVisibleMemorySize) * 100, 2)

                $status = [PSCustomObject]@{
                    hostname = $env:COMPUTERNAME
                    workerName = $script:Config.workerName
                    cpuPercent = $cpuLoad
                    memoryPercent = $memoryUsedPct
                    uptime = (Get-Date) - (Get-CimInstance -ClassName Win32_OperatingSystem).LastBootUpTime
                    runningJobs = $script:RunningJobs.Count
                    timestamp = (Get-Date).ToString("o")
                }

                $result.output = $status | ConvertTo-Json
                $result.exitCode = 0
            }

            "file-transfer" {
                # Copy file to/from specified location
                if ($CommandData.direction -eq "upload") {
                    # File content is base64 encoded in the command
                    $bytes = [Convert]::FromBase64String($CommandData.content)
                    [IO.File]::WriteAllBytes($CommandData.destination, $bytes)
                    $result.output = "File uploaded to $($CommandData.destination)"
                } elseif ($CommandData.direction -eq "download") {
                    $bytes = [IO.File]::ReadAllBytes($CommandData.source)
                    $result.output = [Convert]::ToBase64String($bytes)
                }
                $result.exitCode = 0
            }

            default {
                throw "Unknown action: $($CommandData.action)"
            }
        }

        $result.status = "completed"
        Write-Log "Job $jobId completed successfully"

    } catch {
        $result.status = "failed"
        $result.error = $_.Exception.Message
        $result.exitCode = 1
        Write-Log "Job $jobId failed: $($_.Exception.Message)" -Level ERROR
    }

    $endTime = Get-Date
    $result.endTime = $endTime.ToString("o")
    $result.durationMs = [int]($endTime - $startTime).TotalMilliseconds

    # Write result file
    $resultFile = Join-Path $script:Config.resultsFolder "$jobId.json"
    $result | ConvertTo-Json -Depth 10 | Set-Content -Path $resultFile -Encoding UTF8

    # Move command file to completed/failed folder
    $destFolder = if ($result.status -eq "completed") { "completed" } else { "failed" }
    $destPath = Join-Path $script:Config.watchFolder $destFolder (Split-Path $CommandFile -Leaf)
    Move-Item -Path $CommandFile -Destination $destPath -Force -ErrorAction SilentlyContinue

    return $result
}

function Process-CommandFile {
    param([string]$FilePath)

    try {
        # Small delay to ensure file is fully written
        Start-Sleep -Milliseconds 100

        $content = Get-Content -Path $FilePath -Raw -ErrorAction Stop
        $command = $content | ConvertFrom-Json

        if (-not $command.id) {
            $command | Add-Member -NotePropertyName "id" -NotePropertyValue ([guid]::NewGuid().ToString())
        }

        Write-Log "Processing command file: $(Split-Path $FilePath -Leaf) (Job: $($command.id))"

        # Move to processing folder
        $processingPath = Join-Path $script:Config.watchFolder "processing" (Split-Path $FilePath -Leaf)
        Move-Item -Path $FilePath -Destination $processingPath -Force

        # Execute the command
        Invoke-CommandJob -CommandData $command -CommandFile $processingPath

    } catch {
        Write-Log "Error processing file $FilePath : $($_.Exception.Message)" -Level ERROR
    }
}

function Start-FolderWatcher {
    Write-Log "Starting folder watcher on: $($script:Config.watchFolder)"

    # Process any existing files first
    $existingFiles = Get-ChildItem -Path $script:Config.watchFolder -Filter "*.json" -File
    foreach ($file in $existingFiles) {
        Process-CommandFile -FilePath $file.FullName
    }

    # Set up FileSystemWatcher
    $script:Watcher = New-Object System.IO.FileSystemWatcher
    $script:Watcher.Path = $script:Config.watchFolder
    $script:Watcher.Filter = "*.json"
    $script:Watcher.IncludeSubdirectories = $false
    $script:Watcher.EnableRaisingEvents = $true

    # Register for Created events
    $action = {
        $path = $Event.SourceEventArgs.FullPath
        $name = $Event.SourceEventArgs.Name

        # Skip files in subfolders
        if ($path -notmatch "\\(processing|completed|failed)\\") {
            Process-CommandFile -FilePath $path
        }
    }

    Register-ObjectEvent -InputObject $script:Watcher -EventName Created -Action $action -SourceIdentifier "FileCreated"

    Write-Log "Folder watcher started successfully"
}

function Stop-Service {
    Write-Log "Stopping Remote Worker Service..."
    $script:Running = $false

    if ($script:Watcher) {
        $script:Watcher.EnableRaisingEvents = $false
        $script:Watcher.Dispose()
    }

    Unregister-Event -SourceIdentifier "FileCreated" -ErrorAction SilentlyContinue

    Write-Log "Service stopped"
}

function Start-Service {
    Write-Log "============================================"
    Write-Log "Remote Worker Service Starting"
    Write-Log "============================================"

    try {
        Initialize-Config -Path $ConfigPath
        Start-FolderWatcher

        Write-Log "Service is running. Press Ctrl+C to stop."

        # Keep the script running
        while ($script:Running) {
            Start-Sleep -Seconds 1

            # Periodic cleanup of old logs
            if ((Get-Date).Minute -eq 0 -and (Get-Date).Second -lt 2) {
                $cutoffDate = (Get-Date).AddDays(-$script:Config.logRetentionDays)
                Get-ChildItem -Path $script:Config.logsFolder -Filter "*.log" |
                    Where-Object { $_.LastWriteTime -lt $cutoffDate } |
                    Remove-Item -Force -ErrorAction SilentlyContinue
            }
        }

    } catch {
        Write-Log "Fatal error: $($_.Exception.Message)" -Level ERROR
        throw
    } finally {
        Stop-Service
    }
}

# Handle Ctrl+C gracefully
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action { Stop-Service }

# Start the service
Start-Service
