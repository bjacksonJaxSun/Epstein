#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Installs the Remote Worker Service as a Windows service or scheduled task.

.DESCRIPTION
    This script installs the Remote Worker Service to run on system startup.
    It supports two methods:
    - Task Scheduler (default, no dependencies)
    - NSSM (more robust, requires NSSM to be installed)

.PARAMETER Method
    Installation method: "TaskScheduler" or "NSSM"

.PARAMETER Uninstall
    Remove the service instead of installing

.PARAMETER InstallPath
    Where to install the service files (default: C:\ProgramData\RemoteWorker)

.EXAMPLE
    .\Install-Service.ps1
    .\Install-Service.ps1 -Method NSSM
    .\Install-Service.ps1 -Uninstall
#>

param(
    [ValidateSet("TaskScheduler", "NSSM")]
    [string]$Method = "TaskScheduler",

    [switch]$Uninstall,

    [string]$InstallPath = "C:\ProgramData\RemoteWorker",

    [string]$WorkerName = "Worker-01"
)

$ServiceName = "RemoteWorkerService"
$TaskName = "RemoteWorkerService"

function Install-WithTaskScheduler {
    Write-Host "Installing Remote Worker Service using Task Scheduler..." -ForegroundColor Cyan

    # Create installation directory
    if (-not (Test-Path $InstallPath)) {
        New-Item -Path $InstallPath -ItemType Directory -Force | Out-Null
    }

    # Create subdirectories
    @("commands", "results", "logs", "scripts", "commands\processing", "commands\completed", "commands\failed") | ForEach-Object {
        $dir = Join-Path $InstallPath $_
        if (-not (Test-Path $dir)) {
            New-Item -Path $dir -ItemType Directory -Force | Out-Null
        }
    }

    # Copy scripts
    $sourceScript = Join-Path $PSScriptRoot "RemoteWorkerService.ps1"
    $destScript = Join-Path $InstallPath "scripts\RemoteWorkerService.ps1"
    Copy-Item -Path $sourceScript -Destination $destScript -Force

    # Create config file
    $config = @{
        watchFolder = "$InstallPath\commands"
        resultsFolder = "$InstallPath\results"
        logsFolder = "$InstallPath\logs"
        pollIntervalMs = 1000
        commandTimeoutSeconds = 300
        allowedCommands = @()
        blockedCommands = @("Remove-Item -Recurse C:\", "Format-", "Clear-Disk")
        maxConcurrentJobs = 3
        enableLogging = $true
        logRetentionDays = 30
        workerName = $WorkerName
    }

    $configPath = Join-Path $InstallPath "config.json"
    $config | ConvertTo-Json -Depth 5 | Set-Content -Path $configPath -Encoding UTF8

    # Create the scheduled task
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$destScript`" -ConfigPath `"$configPath`""

    $trigger = New-ScheduledTaskTrigger -AtStartup
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

    # Remove existing task if present
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

    # Register new task
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "Remote Worker Service - Monitors folder for commands and executes them"

    Write-Host ""
    Write-Host "Installation complete!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Service Details:" -ForegroundColor Yellow
    Write-Host "  Install Path:    $InstallPath"
    Write-Host "  Commands Folder: $InstallPath\commands"
    Write-Host "  Results Folder:  $InstallPath\results"
    Write-Host "  Logs Folder:     $InstallPath\logs"
    Write-Host "  Worker Name:     $WorkerName"
    Write-Host ""
    Write-Host "To start the service now:" -ForegroundColor Yellow
    Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
    Write-Host ""
    Write-Host "To share the commands folder via Tailscale:" -ForegroundColor Yellow
    Write-Host "  1. Right-click $InstallPath\commands"
    Write-Host "  2. Properties > Sharing > Share..."
    Write-Host "  3. Add 'Everyone' with Read/Write permissions"
    Write-Host ""
}

function Install-WithNSSM {
    Write-Host "Installing Remote Worker Service using NSSM..." -ForegroundColor Cyan

    # Check if NSSM is available
    $nssm = Get-Command nssm -ErrorAction SilentlyContinue
    if (-not $nssm) {
        Write-Host "NSSM not found. Installing via winget..." -ForegroundColor Yellow
        winget install --id=NSSM.NSSM -e --accept-source-agreements

        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

        $nssm = Get-Command nssm -ErrorAction SilentlyContinue
        if (-not $nssm) {
            throw "Failed to install NSSM. Please install manually from https://nssm.cc/"
        }
    }

    # Create installation directory
    if (-not (Test-Path $InstallPath)) {
        New-Item -Path $InstallPath -ItemType Directory -Force | Out-Null
    }

    # Create subdirectories
    @("commands", "results", "logs", "scripts", "commands\processing", "commands\completed", "commands\failed") | ForEach-Object {
        $dir = Join-Path $InstallPath $_
        if (-not (Test-Path $dir)) {
            New-Item -Path $dir -ItemType Directory -Force | Out-Null
        }
    }

    # Copy scripts
    $sourceScript = Join-Path $PSScriptRoot "RemoteWorkerService.ps1"
    $destScript = Join-Path $InstallPath "scripts\RemoteWorkerService.ps1"
    Copy-Item -Path $sourceScript -Destination $destScript -Force

    # Create config file
    $config = @{
        watchFolder = "$InstallPath\commands"
        resultsFolder = "$InstallPath\results"
        logsFolder = "$InstallPath\logs"
        pollIntervalMs = 1000
        commandTimeoutSeconds = 300
        allowedCommands = @()
        blockedCommands = @("Remove-Item -Recurse C:\", "Format-", "Clear-Disk")
        maxConcurrentJobs = 3
        enableLogging = $true
        logRetentionDays = 30
        workerName = $WorkerName
    }

    $configPath = Join-Path $InstallPath "config.json"
    $config | ConvertTo-Json -Depth 5 | Set-Content -Path $configPath -Encoding UTF8

    # Remove existing service if present
    & nssm stop $ServiceName 2>$null
    & nssm remove $ServiceName confirm 2>$null

    # Install service with NSSM
    & nssm install $ServiceName powershell.exe "-NoProfile -ExecutionPolicy Bypass -File `"$destScript`" -ConfigPath `"$configPath`""
    & nssm set $ServiceName AppDirectory $InstallPath
    & nssm set $ServiceName DisplayName "Remote Worker Service"
    & nssm set $ServiceName Description "Monitors folder for commands and executes them for remote workload distribution"
    & nssm set $ServiceName Start SERVICE_AUTO_START
    & nssm set $ServiceName AppStdout "$InstallPath\logs\service-stdout.log"
    & nssm set $ServiceName AppStderr "$InstallPath\logs\service-stderr.log"
    & nssm set $ServiceName AppRotateFiles 1
    & nssm set $ServiceName AppRotateBytes 10485760

    Write-Host ""
    Write-Host "Installation complete!" -ForegroundColor Green
    Write-Host ""
    Write-Host "To start the service:" -ForegroundColor Yellow
    Write-Host "  nssm start $ServiceName"
    Write-Host "  - or -"
    Write-Host "  Start-Service $ServiceName"
    Write-Host ""
}

function Uninstall-Service {
    Write-Host "Uninstalling Remote Worker Service..." -ForegroundColor Cyan

    # Try Task Scheduler
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Removed scheduled task: $TaskName" -ForegroundColor Green
    }

    # Try NSSM
    $nssm = Get-Command nssm -ErrorAction SilentlyContinue
    if ($nssm) {
        & nssm stop $ServiceName 2>$null
        & nssm remove $ServiceName confirm 2>$null
        Write-Host "Removed NSSM service: $ServiceName" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "Service uninstalled." -ForegroundColor Green
    Write-Host "Note: Service files at $InstallPath were NOT removed." -ForegroundColor Yellow
    Write-Host "To remove files: Remove-Item -Path '$InstallPath' -Recurse -Force" -ForegroundColor Yellow
}

# Main execution
if ($Uninstall) {
    Uninstall-Service
} else {
    switch ($Method) {
        "TaskScheduler" { Install-WithTaskScheduler }
        "NSSM" { Install-WithNSSM }
    }
}
