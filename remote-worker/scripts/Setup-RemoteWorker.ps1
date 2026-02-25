#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Complete setup script for Remote Worker on a remote machine.

.DESCRIPTION
    Run this script on the remote worker machine (e.g., bobbyhomeep) to:
    1. Create the installation directory
    2. Install the service
    3. Create and share the commands folder
    4. Start the service

.PARAMETER WorkerName
    Name for this worker (appears in logs and results)

.PARAMETER InstallPath
    Installation directory (default: C:\ProgramData\RemoteWorker)

.PARAMETER ShareName
    Network share name (default: RemoteWorker)

.EXAMPLE
    .\Setup-RemoteWorker.ps1 -WorkerName "HomePC"
#>

param(
    [string]$WorkerName = "Worker-01",
    [string]$InstallPath = "C:\ProgramData\RemoteWorker",
    [string]$ShareName = "RemoteWorker"
)

Write-Host @"

  ============================================
  Remote Worker Setup
  ============================================

"@ -ForegroundColor Cyan

# Step 1: Create directory structure
Write-Host "[1/5] Creating directory structure..." -ForegroundColor Yellow

$directories = @(
    $InstallPath,
    "$InstallPath\commands",
    "$InstallPath\commands\processing",
    "$InstallPath\commands\completed",
    "$InstallPath\commands\failed",
    "$InstallPath\results",
    "$InstallPath\logs",
    "$InstallPath\scripts"
)

foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -Path $dir -ItemType Directory -Force | Out-Null
        Write-Host "  Created: $dir" -ForegroundColor Gray
    }
}

Write-Host "  Directory structure created" -ForegroundColor Green

# Step 2: Copy service script
Write-Host "[2/5] Installing service script..." -ForegroundColor Yellow

$serviceScript = @'
#Requires -Version 5.1
# Remote Worker Service - See full script for documentation

param(
    [string]$ConfigPath = "$PSScriptRoot\..\config.json"
)

$script:RunningJobs = @{}
$script:Config = $null
$script:Watcher = $null
$script:Running = $true

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    switch ($Level) {
        'ERROR' { Write-Host $logEntry -ForegroundColor Red }
        'WARN'  { Write-Host $logEntry -ForegroundColor Yellow }
        'DEBUG' { Write-Host $logEntry -ForegroundColor Gray }
        default { Write-Host $logEntry }
    }
    if ($script:Config.enableLogging -and $script:Config.logsFolder) {
        $logFile = Join-Path $script:Config.logsFolder "worker-$(Get-Date -Format 'yyyy-MM-dd').log"
        Add-Content -Path $logFile -Value $logEntry -ErrorAction SilentlyContinue
    }
}

function Initialize-Config {
    param([string]$Path)
    if (-not (Test-Path $Path)) { throw "Config not found: $Path" }
    $script:Config = Get-Content $Path -Raw | ConvertFrom-Json
    @($script:Config.watchFolder, $script:Config.resultsFolder, $script:Config.logsFolder) | ForEach-Object {
        if (-not (Test-Path $_)) { New-Item -Path $_ -ItemType Directory -Force | Out-Null }
    }
    Write-Log "Configuration loaded. Worker: $($script:Config.workerName)"
}

function Test-CommandAllowed {
    param([string]$Command)
    foreach ($blocked in $script:Config.blockedCommands) {
        if ($Command -match [regex]::Escape($blocked)) { return $false }
    }
    if ($script:Config.allowedCommands.Count -eq 0) { return $true }
    foreach ($allowed in $script:Config.allowedCommands) {
        if ($Command -match [regex]::Escape($allowed)) { return $true }
    }
    return $false
}

function Invoke-CommandJob {
    param([PSCustomObject]$CommandData, [string]$CommandFile)
    $jobId = $CommandData.id
    $startTime = Get-Date
    $result = [PSCustomObject]@{
        id = $jobId; workerName = $script:Config.workerName; status = "running"
        startTime = $startTime.ToString("o"); endTime = $null; durationMs = $null
        exitCode = $null; output = $null; error = $null
        command = $CommandData.command; action = $CommandData.action
    }
    try {
        Write-Log "Executing job $jobId : $($CommandData.action)"
        if (-not (Test-CommandAllowed -Command $CommandData.command)) { throw "Command blocked by policy" }
        $timeout = if ($CommandData.timeout) { $CommandData.timeout } else { $script:Config.commandTimeoutSeconds }
        switch ($CommandData.action.ToLower()) {
            "powershell" {
                $scriptBlock = [ScriptBlock]::Create($CommandData.command)
                $job = Start-Job -ScriptBlock $scriptBlock
                $null = $job | Wait-Job -Timeout $timeout
                if ($job.State -eq 'Running') { $job | Stop-Job; $job | Remove-Job -Force; throw "Timeout after $timeout s" }
                $result.output = ($job | Receive-Job) | Out-String
                $result.exitCode = 0
                $job | Remove-Job -Force
            }
            "process-start" {
                $params = @{ FilePath = $CommandData.command; PassThru = $true }
                if ($CommandData.arguments) { $params.ArgumentList = $CommandData.arguments }
                if ($CommandData.workingDirectory) { $params.WorkingDirectory = $CommandData.workingDirectory }
                $process = Start-Process @params
                $result.output = "Process started with PID: $($process.Id)"
                $result.exitCode = 0
            }
            "process-stop" {
                $process = $null
                if ($CommandData.processId) { $process = Get-Process -Id $CommandData.processId -ErrorAction SilentlyContinue }
                elseif ($CommandData.processName) { $process = Get-Process -Name $CommandData.processName -ErrorAction SilentlyContinue }
                if ($process) { $process | Stop-Process -Force; $result.output = "Process stopped"; $result.exitCode = 0 }
                else { throw "Process not found" }
            }
            "cmd" {
                $psi = New-Object System.Diagnostics.ProcessStartInfo
                $psi.FileName = "cmd.exe"; $psi.Arguments = "/c $($CommandData.command)"
                $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
                $psi.UseShellExecute = $false; $psi.CreateNoWindow = $true
                $proc = New-Object System.Diagnostics.Process; $proc.StartInfo = $psi; $proc.Start() | Out-Null
                $result.output = $proc.StandardOutput.ReadToEnd()
                $stderr = $proc.StandardError.ReadToEnd(); if ($stderr) { $result.error = $stderr }
                $proc.WaitForExit($timeout * 1000); $result.exitCode = $proc.ExitCode
            }
            "status" {
                $cpu = (Get-CimInstance Win32_Processor | Measure-Object LoadPercentage -Average).Average
                $mem = Get-CimInstance Win32_OperatingSystem
                $memPct = [math]::Round((($mem.TotalVisibleMemorySize - $mem.FreePhysicalMemory) / $mem.TotalVisibleMemorySize) * 100, 2)
                $status = @{ hostname = $env:COMPUTERNAME; workerName = $script:Config.workerName; cpuPercent = $cpu; memoryPercent = $memPct; timestamp = (Get-Date).ToString("o") }
                $result.output = $status | ConvertTo-Json; $result.exitCode = 0
            }
            "file-transfer" {
                if ($CommandData.direction -eq "upload") {
                    $bytes = [Convert]::FromBase64String($CommandData.content)
                    [IO.File]::WriteAllBytes($CommandData.destination, $bytes)
                    $result.output = "File uploaded to $($CommandData.destination)"
                } elseif ($CommandData.direction -eq "download") {
                    $bytes = [IO.File]::ReadAllBytes($CommandData.source)
                    $result.output = [Convert]::ToBase64String($bytes)
                }
                $result.exitCode = 0
            }
            "service-update" {
                $scriptPath = Join-Path $PSScriptRoot "RemoteWorkerService.ps1"
                $backupPath = Join-Path $PSScriptRoot "RemoteWorkerService.ps1.bak"
                # Backup current script
                if (Test-Path $scriptPath) { Copy-Item -Path $scriptPath -Destination $backupPath -Force }
                # Write new script
                $newContent = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($CommandData.content))
                Set-Content -Path $scriptPath -Value $newContent -Encoding UTF8
                $result.output = "Service script updated. Scheduling restart..."
                $result.exitCode = 0
                # Schedule restart in 3 seconds (allows result to be written first)
                $restartScript = "Start-Sleep -Seconds 3; Stop-ScheduledTask -TaskName 'RemoteWorkerService'; Start-Sleep -Seconds 2; Start-ScheduledTask -TaskName 'RemoteWorkerService'"
                Start-Process powershell -ArgumentList "-WindowStyle Hidden -Command `"$restartScript`"" -WindowStyle Hidden
            }
            "service-rollback" {
                $scriptPath = Join-Path $PSScriptRoot "RemoteWorkerService.ps1"
                $backupPath = Join-Path $PSScriptRoot "RemoteWorkerService.ps1.bak"
                if (-not (Test-Path $backupPath)) { throw "No backup found to rollback" }
                Copy-Item -Path $backupPath -Destination $scriptPath -Force
                $result.output = "Service rolled back to previous version. Scheduling restart..."
                $result.exitCode = 0
                $restartScript = "Start-Sleep -Seconds 3; Stop-ScheduledTask -TaskName 'RemoteWorkerService'; Start-Sleep -Seconds 2; Start-ScheduledTask -TaskName 'RemoteWorkerService'"
                Start-Process powershell -ArgumentList "-WindowStyle Hidden -Command `"$restartScript`"" -WindowStyle Hidden
            }
            "service-version" {
                $scriptPath = Join-Path $PSScriptRoot "RemoteWorkerService.ps1"
                $scriptContent = Get-Content $scriptPath -Raw
                $hash = [System.BitConverter]::ToString((New-Object System.Security.Cryptography.SHA256Managed).ComputeHash([Text.Encoding]::UTF8.GetBytes($scriptContent))).Replace("-","").Substring(0,16)
                $lastWrite = (Get-Item $scriptPath).LastWriteTime.ToString("o")
                $result.output = @{ scriptHash = $hash; lastModified = $lastWrite; workerName = $script:Config.workerName } | ConvertTo-Json
                $result.exitCode = 0
            }
            default { throw "Unknown action: $($CommandData.action)" }
        }
        $result.status = "completed"
        Write-Log "Job $jobId completed"
    } catch {
        $result.status = "failed"; $result.error = $_.Exception.Message; $result.exitCode = 1
        Write-Log "Job $jobId failed: $($_.Exception.Message)" -Level ERROR
    }
    $endTime = Get-Date
    $result.endTime = $endTime.ToString("o"); $result.durationMs = [int]($endTime - $startTime).TotalMilliseconds
    $resultFile = Join-Path $script:Config.resultsFolder "$jobId.json"
    $result | ConvertTo-Json -Depth 10 | Set-Content -Path $resultFile -Encoding UTF8
    $destFolder = if ($result.status -eq "completed") { "completed" } else { "failed" }
    $destPath = Join-Path (Join-Path $script:Config.watchFolder $destFolder) (Split-Path $CommandFile -Leaf)
    Move-Item -Path $CommandFile -Destination $destPath -Force -ErrorAction SilentlyContinue
    return $result
}

function Process-CommandFile {
    param([string]$FilePath)
    try {
        Start-Sleep -Milliseconds 100
        $command = Get-Content $FilePath -Raw | ConvertFrom-Json
        if (-not $command.id) { $command | Add-Member -NotePropertyName "id" -NotePropertyValue ([guid]::NewGuid().ToString()) }
        Write-Log "Processing: $($command.id)"
        $processingPath = Join-Path (Join-Path $script:Config.watchFolder "processing") (Split-Path $FilePath -Leaf)
        Move-Item -Path $FilePath -Destination $processingPath -Force
        Invoke-CommandJob -CommandData $command -CommandFile $processingPath
    } catch { Write-Log "Error: $($_.Exception.Message)" -Level ERROR }
}

function Start-FolderWatcher {
    Write-Log "Starting watcher on: $($script:Config.watchFolder)"
    Get-ChildItem -Path $script:Config.watchFolder -Filter "*.json" -File | ForEach-Object { Process-CommandFile $_.FullName }
    $script:Watcher = New-Object System.IO.FileSystemWatcher
    $script:Watcher.Path = $script:Config.watchFolder
    $script:Watcher.Filter = "*.json"
    $script:Watcher.IncludeSubdirectories = $false
    $script:Watcher.EnableRaisingEvents = $true
    $action = { $path = $Event.SourceEventArgs.FullPath; if ($path -notmatch "\\(processing|completed|failed)\\") { Process-CommandFile -FilePath $path } }
    Register-ObjectEvent -InputObject $script:Watcher -EventName Created -Action $action -SourceIdentifier "FileCreated"
    Write-Log "Watcher started"
}

Write-Log "============================================"
Write-Log "Remote Worker Service Starting"
Write-Log "============================================"
Initialize-Config -Path $ConfigPath
Start-FolderWatcher
Write-Log "Service running. Press Ctrl+C to stop."
while ($script:Running) { Start-Sleep -Seconds 1 }
'@

$scriptPath = "$InstallPath\scripts\RemoteWorkerService.ps1"
$serviceScript | Set-Content -Path $scriptPath -Encoding UTF8
Write-Host "  Service script installed" -ForegroundColor Green

# Step 3: Create config
Write-Host "[3/5] Creating configuration..." -ForegroundColor Yellow

$config = @{
    watchFolder = "$InstallPath\commands"
    resultsFolder = "$InstallPath\results"
    logsFolder = "$InstallPath\logs"
    pollIntervalMs = 1000
    commandTimeoutSeconds = 300
    allowedCommands = @()
    blockedCommands = @("Remove-Item -Recurse C:\", "Format-", "Clear-Disk", "rd /s")
    maxConcurrentJobs = 3
    enableLogging = $true
    logRetentionDays = 30
    workerName = $WorkerName
}

$configPath = "$InstallPath\config.json"
$config | ConvertTo-Json -Depth 5 | Set-Content -Path $configPath -Encoding UTF8
Write-Host "  Configuration created" -ForegroundColor Green

# Step 4: Create network share
Write-Host "[4/5] Creating network share..." -ForegroundColor Yellow

# Remove existing share if present
$existingShare = Get-SmbShare -Name $ShareName -ErrorAction SilentlyContinue
if ($existingShare) {
    Remove-SmbShare -Name $ShareName -Force -ErrorAction SilentlyContinue
    Write-Host "  Removed existing share" -ForegroundColor Gray
}

# Create new share with full access
New-SmbShare -Name $ShareName -Path $InstallPath -FullAccess "Everyone" | Out-Null

# Set NTFS permissions
$acl = Get-Acl $InstallPath
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("Everyone", "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow")
$acl.SetAccessRule($rule)
Set-Acl -Path $InstallPath -AclObject $acl

Write-Host "  Share created: \\$env:COMPUTERNAME\$ShareName" -ForegroundColor Green

# Step 5: Create and start scheduled task
Write-Host "[5/5] Installing service..." -ForegroundColor Yellow

$taskName = "RemoteWorkerService"

# Remove existing task
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

# Create task
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$scriptPath`" -ConfigPath `"$configPath`""
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Remote Worker Service" | Out-Null

# Start the task
Start-ScheduledTask -TaskName $taskName

Write-Host "  Service installed and started" -ForegroundColor Green

# Summary
$tailscaleIP = & "C:\Program Files\Tailscale\tailscale.exe" ip -4 2>$null
if (-not $tailscaleIP) { $tailscaleIP = "Unknown (run 'tailscale ip' to find)" }

Write-Host @"

  ============================================
  Setup Complete!
  ============================================

  Worker Name:     $WorkerName
  Install Path:    $InstallPath
  Network Share:   \\$env:COMPUTERNAME\$ShareName
  Tailscale IP:    $tailscaleIP

  From your control machine, access:
    Commands: \\$tailscaleIP\$ShareName\commands
    Results:  \\$tailscaleIP\$ShareName\results

  Service Status:
"@ -ForegroundColor Green

Get-ScheduledTask -TaskName $taskName | Format-List TaskName, State

Write-Host @"

  To test, create a file with this content in the commands folder:
  {
    "id": "test-001",
    "action": "powershell",
    "command": "Get-Date"
  }

"@ -ForegroundColor Cyan
