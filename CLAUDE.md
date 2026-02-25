# Epstein Dashboard Project

## Overview
This project contains the Epstein Dashboard - a document analysis and visualization platform with a .NET Core backend and React frontend.

## Project Structure
```
EpsteinDownloader/
├── dashboard/
│   ├── backend/           # .NET Core API
│   │   └── src/
│   │       ├── EpsteinDashboard.Api/          # Web API layer
│   │       ├── EpsteinDashboard.Application/  # Application services
│   │       ├── EpsteinDashboard.Core/         # Domain entities
│   │       └── EpsteinDashboard.Infrastructure/ # Data access
│   ├── frontend/          # React/TypeScript frontend
│   ├── deploy-lynnox.sh   # Full deployment script
│   └── epstein-dashboard.service  # Systemd service file
└── epstein_extraction/    # Python extraction scripts
```

## Azure VM Deployment (Lynnox)

### Connection Details
- **VM IP:** 20.25.96.123
- **Username:** azureuser
- **Dashboard Path:** /data/dashboard
- **Backend URL:** http://20.25.96.123:5000

### Quick Deployment Commands

**Full deployment (build and restart):**
```bash
ssh azureuser@20.25.96.123 "cd /data/dashboard && ./deploy-lynnox.sh"
```

**Restart only (no rebuild):**
```bash
ssh azureuser@20.25.96.123 "cd /data/dashboard && ./deploy-lynnox.sh --restart"
```

**Frontend only:**
```bash
ssh azureuser@20.25.96.123 "cd /data/dashboard && ./deploy-lynnox.sh --frontend"
```

**Backend only:**
```bash
ssh azureuser@20.25.96.123 "cd /data/dashboard && ./deploy-lynnox.sh --backend"
```

### Syncing Code to VM

**Sync entire dashboard:**
```bash
# First, clean permissions on remote
ssh azureuser@20.25.96.123 "sudo chown -R azureuser:azureuser /data/dashboard"

# Sync backend source (not bin/obj)
scp -r dashboard/backend/src/* azureuser@20.25.96.123:/data/dashboard/backend/src/

# Sync frontend source
scp -r dashboard/frontend/src/* azureuser@20.25.96.123:/data/dashboard/frontend/src/

# Sync config files
scp dashboard/frontend/package.json azureuser@20.25.96.123:/data/dashboard/frontend/
scp dashboard/frontend/vite.config.ts azureuser@20.25.96.123:/data/dashboard/frontend/
```

### Service Management

**View logs:**
```bash
ssh azureuser@20.25.96.123 "tail -f /var/log/epstein-dashboard.log"
```

**Check status:**
```bash
ssh azureuser@20.25.96.123 "ps aux | grep EpsteinDashboard"
```

**Health check:**
```bash
ssh azureuser@20.25.96.123 "curl http://localhost:5000/health"
```

**Stop service:**
```bash
ssh azureuser@20.25.96.123 "pkill -f 'EpsteinDashboard.Api.dll'"
```

### Database

**Connection String:** `Host=localhost;Database=epstein_documents;Username=epstein_user;Password=epstein_secure_pw_2024`

**Check database:**
```bash
ssh azureuser@20.25.96.123 "PGPASSWORD=epstein_secure_pw_2024 psql -h localhost -U epstein_user -d epstein_documents -c 'SELECT COUNT(*) FROM documents;'"
```

**Check auth tables:**
```bash
ssh azureuser@20.25.96.123 "PGPASSWORD=epstein_secure_pw_2024 psql -h localhost -U epstein_user -d epstein_documents -c \"SELECT tablename FROM pg_tables WHERE tablename IN ('users', 'roles', 'user_roles', 'refresh_tokens');\""
```

### Default Admin Credentials
- **Username:** admin
- **Password:** ChangeMe123!
- **Email:** admin@epsteindashboard.local

### Authentication System

The dashboard uses JWT-based authentication with role-based access control:

| Role     | Tier Level | Access                                    |
|----------|------------|-------------------------------------------|
| freemium | 0          | Dashboard overview, sample data           |
| basic    | 1          | People, Documents, Media, Network, etc.   |
| premium  | 2          | AI Insights, advanced analysis features   |
| admin    | 3          | Full system access, user management       |

### Common Issues

**Permission denied during build:**
```bash
ssh azureuser@20.25.96.123 "sudo chown -R azureuser:azureuser /data/dashboard && rm -rf /data/dashboard/backend/src/*/bin /data/dashboard/backend/src/*/obj"
```

**Service won't start:**
1. Check if port 5000 is already in use: `ss -tlnp | grep 5000`
2. Kill existing process: `pkill -f 'dotnet'`
3. Check logs: `tail -100 /var/log/epstein-dashboard.log`

**Frontend build fails with TypeScript errors:**
Check for missing types or unused imports. Run `npm run build` locally first to catch errors.

### API Endpoints

- **Health:** GET /health
- **Swagger:** GET /swagger
- **Auth:** POST /api/auth/login, POST /api/auth/refresh
- **Documents:** GET /api/documents
- **People:** GET /api/people
- **Media:** GET /api/media
- **Search:** GET /api/search

## Local Development

### Backend
```bash
cd dashboard/backend
dotnet restore
dotnet run --project src/EpsteinDashboard.Api
```

### Frontend
```bash
cd dashboard/frontend
npm install
npm run dev
```

Frontend dev server runs on http://localhost:5173 with proxy to backend at localhost:5203.

## Remote Worker System (bobbyhomeep)

A Tailscale-based system for executing commands on remote machines via file-based job queues.

### Quick Start

```powershell
# Import the client module
Import-Module "D:\Personal\Epstein\remote-worker\scripts\RemoteWorkerClient.ps1"

# Check worker status
Get-RemoteStatus

# Run PowerShell commands
Invoke-RemotePowerShell "Get-Process | Select -First 5"

# Run CMD commands
Invoke-RemoteCmd "dir C:\Temp"

# Start a process
Start-RemoteProcess "python.exe" -Arguments "C:\scripts\task.py"

# Stop a process
Stop-RemoteProcess -ProcessName "python"

# Transfer files
Send-FileToWorker -LocalPath "C:\local\file.txt" -RemotePath "C:\Temp\file.txt"
Get-FileFromWorker -RemotePath "C:\Temp\results.csv" -LocalPath "C:\local\results.csv"
```

### Worker Configuration

| Setting | Value |
|---------|-------|
| Worker Name | bobbyhomeep |
| Tailscale IP | 100.75.137.22 |
| Commands Share | `\\100.75.137.22\RemoteWorker\commands` |
| Results Share | `\\100.75.137.22\RemoteWorker\results` |

### Installing on a New Worker

Run as Administrator on the target machine:
```powershell
.\remote-worker\scripts\Setup-RemoteWorker.ps1 -WorkerName "WorkerName"
```

### Files

- Client module: `remote-worker/scripts/RemoteWorkerClient.ps1`
- Setup script: `remote-worker/scripts/Setup-RemoteWorker.ps1`
- Service script: `remote-worker/scripts/RemoteWorkerService.ps1`
- Full documentation: `remote-worker/README.md`
- Claude skill: `.claude/skills/remote-worker.md`
