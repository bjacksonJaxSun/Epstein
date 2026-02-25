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
Invoke-RemotePowerShell "Get-Content 'C:\RemoteWorker\logs\worker-$(Get-Date -Format yyyy-MM-dd).log' -Tail 20"
```

### Kill Stuck Process
```powershell
Stop-RemoteProcess -ProcessName "python"
```

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
