# Remote Worker System

A lightweight workload distribution system using Tailscale and shared folders. Execute commands on remote machines by simply dropping JSON files into a shared folder.

## Architecture

```
┌─────────────────────┐                         ┌─────────────────────┐
│   CONTROL MACHINE   │      Tailscale VPN      │   WORKER MACHINE    │
│   (This PC)         │◄───────────────────────►│   (bobbyhomeep)     │
│                     │                         │                     │
│  Drop command.json  │──► \\worker\commands ──►│  FileSystemWatcher  │
│                     │                         │  picks up & runs    │
│  Read result.json ◄─│◄── \\worker\results  ◄──│  writes result      │
└─────────────────────┘                         └─────────────────────┘
```

## Quick Start

### Step 1: Setup Worker Machine (bobbyhomeep)

1. Copy the `scripts/Setup-RemoteWorker.ps1` to the worker machine
2. Run as Administrator:

```powershell
.\Setup-RemoteWorker.ps1 -WorkerName "HomePC"
```

This automatically:
- Creates `C:\ProgramData\RemoteWorker` with all directories
- Installs the watcher service
- Creates a network share accessible via Tailscale
- Starts the service

### Step 2: Setup Control Machine (This PC)

Import the client module:

```powershell
Import-Module "D:\Personal\Epstein\remote-worker\scripts\RemoteWorkerClient.ps1"
```

Or use the interactive quick sender:

```powershell
.\scripts\Quick-Send.ps1
```

### Step 3: Send Commands

```powershell
# Execute PowerShell commands
Invoke-RemotePowerShell "Get-Process | Select -First 5"

# Get worker status
Get-RemoteStatus

# Start a process
Start-RemoteProcess "notepad.exe"

# Run CMD commands
Invoke-RemoteCmd "dir C:\Temp"
```

## Command File Format

Commands are JSON files dropped into the commands folder:

```json
{
  "id": "unique-job-id",
  "action": "powershell",
  "command": "Get-Process | Where CPU -gt 10",
  "timeout": 60
}
```

### Supported Actions

| Action | Description | Example |
|--------|-------------|---------|
| `powershell` | Run PowerShell code | `Get-Process` |
| `cmd` | Run CMD command | `dir /s` |
| `process-start` | Start executable | `notepad.exe` |
| `process-stop` | Stop process | (use processName/processId) |
| `status` | Get worker stats | CPU, memory, uptime |
| `file-transfer` | Upload/download files | Base64 encoded |
| `service-update` | Update service script | Push new version |
| `service-rollback` | Rollback to previous | Restore backup |
| `service-version` | Get script version | Hash & timestamp |

### Process Start Example

```json
{
  "id": "start-python",
  "action": "process-start",
  "command": "python.exe",
  "arguments": "C:\\scripts\\long_task.py",
  "workingDirectory": "C:\\scripts"
}
```

### Process Stop Example

```json
{
  "id": "stop-notepad",
  "action": "process-stop",
  "processName": "notepad"
}
```

## Result Format

Results appear in the results folder as `{job-id}.json`:

```json
{
  "id": "job-001",
  "workerName": "HomePC",
  "status": "completed",
  "startTime": "2024-01-15T10:30:00Z",
  "endTime": "2024-01-15T10:30:02Z",
  "durationMs": 2150,
  "exitCode": 0,
  "output": "Process list here...",
  "error": null
}
```

## Client Functions

| Function | Description |
|----------|-------------|
| `Invoke-RemotePowerShell` | Run PowerShell on worker |
| `Invoke-RemoteCmd` | Run CMD on worker |
| `Start-RemoteProcess` | Start an executable |
| `Stop-RemoteProcess` | Stop a process |
| `Get-RemoteStatus` | Get CPU/memory/uptime |
| `Send-FileToWorker` | Upload a file |
| `Get-FileFromWorker` | Download a file |
| `Update-RemoteWorkerService` | Push new service script |
| `Get-RemoteWorkerVersion` | Get service version info |
| `Undo-RemoteWorkerUpdate` | Rollback to previous version |
| `Send-RemoteCommand` | Low-level command sender |

## Configuration

Edit `C:\ProgramData\RemoteWorker\config.json` on the worker:

```json
{
  "watchFolder": "C:\\RemoteWorker\\commands",
  "resultsFolder": "C:\\RemoteWorker\\results",
  "logsFolder": "C:\\RemoteWorker\\logs",
  "commandTimeoutSeconds": 300,
  "blockedCommands": ["Format-", "Clear-Disk"],
  "allowedCommands": [],
  "maxConcurrentJobs": 3,
  "workerName": "HomePC"
}
```

### Security

- `blockedCommands`: Patterns that will be rejected (regex)
- `allowedCommands`: If not empty, ONLY these patterns allowed
- The service runs as SYSTEM for full access
- Tailscale provides encrypted transport

## Managing the Service

On the worker machine:

```powershell
# Check status
Get-ScheduledTask -TaskName "RemoteWorkerService"

# Stop service
Stop-ScheduledTask -TaskName "RemoteWorkerService"

# Start service
Start-ScheduledTask -TaskName "RemoteWorkerService"

# View logs
Get-Content "C:\ProgramData\RemoteWorker\logs\worker-*.log" -Tail 50

# Uninstall
Unregister-ScheduledTask -TaskName "RemoteWorkerService" -Confirm:$false
```

## Network Share Access

From control machine, access via Tailscale IP:

```
\\100.75.137.22\RemoteWorker\commands   <- Drop commands here
\\100.75.137.22\RemoteWorker\results    <- Results appear here
\\100.75.137.22\RemoteWorker\logs       <- View logs
```

## Troubleshooting

### Cannot access share

1. Verify Tailscale is connected: `tailscale status`
2. Check share exists on worker: `Get-SmbShare`
3. Test connectivity: `Test-NetConnection 100.75.137.22 -Port 445`

### Commands not executing

1. Check service is running: `Get-ScheduledTask -TaskName "RemoteWorkerService"`
2. View logs: `Get-Content C:\ProgramData\RemoteWorker\logs\worker-*.log -Tail 20`
3. Check for files in `commands\processing` (stuck jobs)

### Permission denied

Ensure the share has correct permissions:
```powershell
Grant-SmbShareAccess -Name "RemoteWorker" -AccountName "Everyone" -AccessRight Full -Force
```

## Files

```
remote-worker/
├── config.json                    # Default config template
├── README.md                      # This file
├── scripts/
│   ├── RemoteWorkerService.ps1    # Main watcher service
│   ├── RemoteWorkerClient.ps1     # Control machine client module
│   ├── Quick-Send.ps1             # Interactive command sender
│   ├── Install-Service.ps1        # Service installer
│   └── Setup-RemoteWorker.ps1     # One-click worker setup
├── commands/                      # Drop commands here (local testing)
├── results/                       # Results appear here
└── logs/                          # Service logs
```
