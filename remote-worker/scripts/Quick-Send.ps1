<#
.SYNOPSIS
    Quick command sender - Simple way to run commands on remote workers.

.DESCRIPTION
    Drag and drop this script to quickly send commands to remote workers.
    Can also be run from command line with parameters.

.EXAMPLE
    .\Quick-Send.ps1 "Get-Process"
    .\Quick-Send.ps1 "dir C:\Temp" -Type cmd
    .\Quick-Send.ps1 "notepad.exe" -Type start
#>

param(
    [Parameter(Position = 0)]
    [string]$Command,

    [ValidateSet("powershell", "cmd", "start", "stop", "status")]
    [string]$Type = "powershell",

    [string]$Worker = "bobbyhomeep",

    [string]$WorkerIP = "100.75.137.22",

    [int]$Timeout = 60
)

# Configuration
$CommandsPath = "\\$WorkerIP\RemoteWorker\commands"
$ResultsPath = "\\$WorkerIP\RemoteWorker\results"

function Send-QuickCommand {
    param($Cmd, $Action, $Tmout)

    $jobId = "quick-$(Get-Date -Format 'HHmmss')-$((Get-Random -Maximum 9999).ToString('D4'))"

    $commandObj = @{
        id = $jobId
        action = $Action
        command = $Cmd
        timeout = $Tmout
        timestamp = (Get-Date).ToString("o")
        source = $env:COMPUTERNAME
    }

    $commandFile = Join-Path $CommandsPath "$jobId.json"
    $commandObj | ConvertTo-Json | Set-Content -Path $commandFile -Encoding UTF8

    Write-Host "Sent job: $jobId" -ForegroundColor Cyan
    Write-Host "Waiting for result..." -ForegroundColor Gray

    $resultFile = Join-Path $ResultsPath "$jobId.json"
    $startTime = Get-Date

    while ((Get-Date) -lt $startTime.AddSeconds($Tmout + 30)) {
        if (Test-Path $resultFile) {
            Start-Sleep -Milliseconds 200
            $result = Get-Content $resultFile -Raw | ConvertFrom-Json

            Write-Host ""
            if ($result.status -eq "completed") {
                Write-Host "=== SUCCESS ===" -ForegroundColor Green
            } else {
                Write-Host "=== FAILED ===" -ForegroundColor Red
            }

            Write-Host "Duration: $($result.durationMs)ms"
            Write-Host ""

            if ($result.output) {
                Write-Host "Output:" -ForegroundColor Yellow
                Write-Host $result.output
            }

            if ($result.error) {
                Write-Host "Error:" -ForegroundColor Red
                Write-Host $result.error
            }

            return
        }
        Start-Sleep -Milliseconds 500
    }

    Write-Host "Timeout waiting for result" -ForegroundColor Red
}

# Interactive mode if no command provided
if (-not $Command) {
    Write-Host @"

  Remote Worker Quick Send
  ========================
  Worker: $Worker ($WorkerIP)

"@ -ForegroundColor Cyan

    Write-Host "Enter command (or 'exit' to quit):"

    while ($true) {
        Write-Host ""
        $input = Read-Host "[$Type]"

        if ($input -eq "exit" -or $input -eq "quit") { break }
        if ($input -eq "") { continue }

        # Check for type switch commands
        if ($input -match "^:(powershell|cmd|start|stop|status)$") {
            $Type = $matches[1]
            Write-Host "Switched to: $Type" -ForegroundColor Yellow
            continue
        }

        if ($input -eq ":help") {
            Write-Host @"
Commands:
  :powershell  - Switch to PowerShell mode
  :cmd         - Switch to CMD mode
  :start       - Switch to process start mode
  :stop        - Switch to process stop mode
  :status      - Get worker status
  :help        - Show this help
  exit         - Quit
"@ -ForegroundColor Gray
            continue
        }

        if ($Type -eq "status") {
            Send-QuickCommand -Cmd "" -Action "status" -Tmout 30
        } else {
            $action = switch ($Type) {
                "start" { "process-start" }
                "stop" { "process-stop" }
                default { $Type }
            }
            Send-QuickCommand -Cmd $input -Action $action -Tmout $Timeout
        }
    }
} else {
    # Direct command mode
    $action = switch ($Type) {
        "start" { "process-start" }
        "stop" { "process-stop" }
        default { $Type }
    }
    Send-QuickCommand -Cmd $Command -Action $action -Tmout $Timeout
}
