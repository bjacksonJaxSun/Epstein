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
│   └── frontend/          # React/TypeScript frontend
└── epstein_extraction/    # Python extraction scripts
```

## Database

**Connection String:** `Host=localhost;Database=epstein_documents;Username=epstein_user;Password=epstein_secure_pw_2024`

**Check database:**
```powershell
$env:PGPASSWORD='epstein_secure_pw_2024'; psql -h localhost -U epstein_user -d epstein_documents -c 'SELECT COUNT(*) FROM documents;'
```

## Default Admin Credentials
- **Username:** admin
- **Password:** ChangeMe123!
- **Email:** admin@epsteindashboard.local

## Authentication System

The dashboard uses JWT-based authentication with role-based access control:

| Role     | Tier Level | Access                                    |
|----------|------------|-------------------------------------------|
| freemium | 0          | Dashboard overview, sample data           |
| basic    | 1          | People, Documents, Media, Network, etc.   |
| premium  | 2          | AI Insights, advanced analysis features   |
| admin    | 3          | Full system access, user management       |

## API Endpoints

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
