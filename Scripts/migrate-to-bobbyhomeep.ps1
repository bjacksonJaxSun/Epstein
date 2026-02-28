# ============================================================================
# Epstein Dashboard Migration Script
# Target: BobbyHomeEP (192.168.12.126)
# Run this script FROM BobbyHomeEP as Administrator
# ============================================================================

param(
    [switch]$SkipPrerequisites,
    [switch]$SkipDatabase,
    [switch]$SkipFiles,
    [switch]$SkipBuild,
    [switch]$UpdatePathsOnly
)

$ErrorActionPreference = "Stop"

# Configuration
$AzureVM = "20.25.96.123"
$AzureUser = "azureuser"
$AzureDbPassword = "epstein_secure_pw_2024"
$LocalDbPassword = "epstein_local_pw_2024"

$AppPath = "C:\EpsteinDashboard"
$DataPath = "D:\EpsteinData"
$PostgresDataPath = "$DataPath\postgres"
$FilesPath = "$DataPath\epstein_files"
$BackupsPath = "$DataPath\backups"

$GitRepo = "https://github.com/bjacksonJaxSun/Epstein.git"

# ============================================================================
# Helper Functions
# ============================================================================

function Write-Step {
    param([string]$Message)
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host $Message -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Test-Command {
    param([string]$Command)
    return $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

# ============================================================================
# Phase 0: Check Prerequisites
# ============================================================================

if (-not $SkipPrerequisites -and -not $UpdatePathsOnly) {
    Write-Step "Phase 0: Checking Prerequisites"

    # Check if running as admin
    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) {
        Write-Error "Please run this script as Administrator"
        exit 1
    }
    Write-Success "Running as Administrator"

    # Check PostgreSQL
    if (Test-Command "psql") {
        $pgVersion = psql --version
        Write-Success "PostgreSQL installed: $pgVersion"
    } else {
        Write-Error "PostgreSQL not found. Please install from https://www.postgresql.org/download/windows/"
        Write-Host "During install, set data directory to: $PostgresDataPath"
        exit 1
    }

    # Check .NET SDK
    if (Test-Command "dotnet") {
        $dotnetVersion = dotnet --version
        Write-Success ".NET SDK installed: $dotnetVersion"
    } else {
        Write-Error ".NET SDK not found. Please install from https://dotnet.microsoft.com/download/dotnet/9.0"
        exit 1
    }

    # Check Node.js
    if (Test-Command "node") {
        $nodeVersion = node --version
        Write-Success "Node.js installed: $nodeVersion"
    } else {
        Write-Error "Node.js not found. Please install from https://nodejs.org/"
        exit 1
    }

    # Check Git
    if (Test-Command "git") {
        $gitVersion = git --version
        Write-Success "Git installed: $gitVersion"
    } else {
        Write-Error "Git not found. Please install from https://git-scm.com/download/win"
        exit 1
    }

    # Check SSH
    if (Test-Command "ssh") {
        Write-Success "SSH available"
    } else {
        Write-Warning "SSH not found. Install OpenSSH or use PuTTY"
    }
}

# ============================================================================
# Phase 1: Create Directory Structure
# ============================================================================

if (-not $UpdatePathsOnly) {
    Write-Step "Phase 1: Creating Directory Structure"

    $directories = @($AppPath, $DataPath, $FilesPath, $BackupsPath)
    foreach ($dir in $directories) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Force -Path $dir | Out-Null
            Write-Success "Created: $dir"
        } else {
            Write-Success "Exists: $dir"
        }
    }
}

# ============================================================================
# Phase 2: Clone/Update Repository
# ============================================================================

if (-not $UpdatePathsOnly) {
    Write-Step "Phase 2: Setting Up Application Code"

    if (Test-Path "$AppPath\.git") {
        Write-Host "Repository exists, pulling latest..."
        Push-Location $AppPath
        git pull
        Pop-Location
        Write-Success "Repository updated"
    } else {
        Write-Host "Cloning repository..."
        git clone $GitRepo $AppPath
        Write-Success "Repository cloned"
    }
}

# ============================================================================
# Phase 3: Export Database from Azure VM
# ============================================================================

if (-not $SkipDatabase -and -not $UpdatePathsOnly) {
    Write-Step "Phase 3: Exporting Database from Azure VM"

    $dumpFile = "$BackupsPath\epstein_backup.dump"

    Write-Host "Creating database dump on Azure VM..."
    Write-Host "You may be prompted for SSH password/key..."

    # Create dump on VM
    $sshCmd = "PGPASSWORD=$AzureDbPassword pg_dump -h localhost -U epstein_user -d epstein_documents -F c -f /tmp/epstein_backup.dump"
    ssh "${AzureUser}@${AzureVM}" $sshCmd

    if ($LASTEXITCODE -eq 0) {
        Write-Success "Database dump created on VM"
    } else {
        Write-Error "Failed to create database dump"
        exit 1
    }

    Write-Host "Downloading database dump (6.1 GB)..."
    scp "${AzureUser}@${AzureVM}:/tmp/epstein_backup.dump" $dumpFile

    if (Test-Path $dumpFile) {
        $size = (Get-Item $dumpFile).Length / 1GB
        Write-Success "Database dump downloaded: $([math]::Round($size, 2)) GB"
    } else {
        Write-Error "Failed to download database dump"
        exit 1
    }
}

# ============================================================================
# Phase 4: Setup Local PostgreSQL
# ============================================================================

if (-not $SkipDatabase -and -not $UpdatePathsOnly) {
    Write-Step "Phase 4: Setting Up Local PostgreSQL"

    Write-Host "Creating database user and database..."

    # Check if user exists
    $userExists = psql -U postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='epstein_user'" 2>$null
    if ($userExists -ne "1") {
        psql -U postgres -c "CREATE USER epstein_user WITH PASSWORD '$LocalDbPassword';"
        Write-Success "Created user: epstein_user"
    } else {
        Write-Success "User exists: epstein_user"
    }

    # Check if database exists
    $dbExists = psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='epstein_documents'" 2>$null
    if ($dbExists -ne "1") {
        psql -U postgres -c "CREATE DATABASE epstein_documents OWNER epstein_user;"
        Write-Success "Created database: epstein_documents"
    } else {
        Write-Warning "Database exists: epstein_documents (will restore over it)"
    }

    Write-Host "Restoring database (this may take a few minutes)..."
    $dumpFile = "$BackupsPath\epstein_backup.dump"
    pg_restore -U postgres -d epstein_documents --clean --if-exists $dumpFile 2>$null

    # Grant permissions
    psql -U postgres -d epstein_documents -c "GRANT ALL ON ALL TABLES IN SCHEMA public TO epstein_user;"
    psql -U postgres -d epstein_documents -c "GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO epstein_user;"

    Write-Success "Database restored and permissions granted"

    # Verify
    $docCount = psql -U postgres -d epstein_documents -tAc "SELECT COUNT(*) FROM documents"
    Write-Success "Documents in database: $docCount"
}

# ============================================================================
# Phase 5: Transfer Document Files
# ============================================================================

if (-not $SkipFiles -and -not $UpdatePathsOnly) {
    Write-Step "Phase 5: Transferring Document Files (102 GB)"

    Write-Host "This will take several hours. Options:"
    Write-Host "  1. Continue with SCP (slow but works)"
    Write-Host "  2. Use existing local files"
    Write-Host "  3. Skip for now"

    $choice = Read-Host "Enter choice (1/2/3)"

    switch ($choice) {
        "1" {
            Write-Host "Starting SCP transfer... (Ctrl+C to cancel)"
            scp -r "${AzureUser}@${AzureVM}:/data/VOL00010/VOL00010/*" "$FilesPath\"
            Write-Success "File transfer complete"
        }
        "2" {
            $localSource = Read-Host "Enter path to existing files (e.g., \\server\share)"
            if (Test-Path $localSource) {
                Write-Host "Copying files with robocopy..."
                robocopy $localSource $FilesPath /E /MT:8 /R:3 /W:5
                Write-Success "File copy complete"
            } else {
                Write-Error "Path not found: $localSource"
            }
        }
        "3" {
            Write-Warning "Skipping file transfer. You'll need to copy files manually."
        }
    }
}

# ============================================================================
# Phase 6: Update Database Paths
# ============================================================================

Write-Step "Phase 6: Updating Database Paths"

Write-Host "Converting Linux paths to Windows paths..."

$pathUpdateSql = @"
-- Update document file paths
UPDATE documents
SET file_path = REPLACE(file_path, '/data/VOL00010/VOL00010/', 'D:\EpsteinData\epstein_files\')
WHERE file_path LIKE '/data/VOL00010/%';

UPDATE documents
SET file_path = REPLACE(file_path, '/data/epstein_files/', 'D:\EpsteinData\epstein_files\')
WHERE file_path LIKE '/data/epstein_files/%';

UPDATE documents
SET file_path = REPLACE(file_path, '/', '\')
WHERE file_path LIKE 'D:%' AND file_path LIKE '%/%';

-- Update media file paths
UPDATE media_files
SET file_path = REPLACE(file_path, '/data/VOL00010/VOL00010/', 'D:\EpsteinData\epstein_files\')
WHERE file_path LIKE '/data/VOL00010/%';

UPDATE media_files
SET file_path = REPLACE(file_path, '/data/epstein_files/', 'D:\EpsteinData\epstein_files\')
WHERE file_path LIKE '/data/epstein_files/%';

UPDATE media_files
SET file_path = REPLACE(file_path, '/', '\')
WHERE file_path LIKE 'D:%' AND file_path LIKE '%/%';
"@

$pathUpdateSql | psql -U postgres -d epstein_documents

Write-Success "Database paths updated"

# Verify paths
$samplePath = psql -U postgres -d epstein_documents -tAc "SELECT file_path FROM documents LIMIT 1"
Write-Host "Sample path: $samplePath"

# ============================================================================
# Phase 7: Configure Application
# ============================================================================

if (-not $UpdatePathsOnly) {
    Write-Step "Phase 7: Configuring Application"

    # Create backend config
    $backendConfig = @"
{
  "ConnectionStrings": {
    "EpsteinDb": "Host=localhost;Database=epstein_documents;Username=epstein_user;Password=$LocalDbPassword"
  },
  "DocumentBasePath": "D:\\EpsteinData\\epstein_files",
  "AllowedOrigins": "http://localhost:5173,http://192.168.12.126:5173,http://BobbyHomeEP:5173",
  "OPENAI_API_KEY": "",
  "Logging": {
    "LogLevel": {
      "Default": "Information"
    }
  }
}
"@

    $backendConfigPath = "$AppPath\dashboard\backend\appsettings.Local.json"
    $backendConfig | Out-File -FilePath $backendConfigPath -Encoding UTF8
    Write-Success "Created: $backendConfigPath"

    # Create frontend config
    $frontendConfig = "VITE_API_URL=http://192.168.12.126:5000"
    $frontendConfigPath = "$AppPath\dashboard\frontend\.env.local"
    $frontendConfig | Out-File -FilePath $frontendConfigPath -Encoding UTF8
    Write-Success "Created: $frontendConfigPath"
}

# ============================================================================
# Phase 8: Build Application
# ============================================================================

if (-not $SkipBuild -and -not $UpdatePathsOnly) {
    Write-Step "Phase 8: Building Application"

    # Build backend
    Write-Host "Building backend..."
    Push-Location "$AppPath\dashboard\backend"
    dotnet restore
    dotnet build -c Release
    Pop-Location
    Write-Success "Backend built"

    # Build frontend
    Write-Host "Building frontend..."
    Push-Location "$AppPath\dashboard\frontend"
    npm install
    npm run build
    Pop-Location
    Write-Success "Frontend built"
}

# ============================================================================
# Phase 9: Configure Firewall
# ============================================================================

if (-not $UpdatePathsOnly) {
    Write-Step "Phase 9: Configuring Firewall"

    # Check if rules exist
    $apiRule = Get-NetFirewallRule -DisplayName "Epstein Dashboard API" -ErrorAction SilentlyContinue
    if (-not $apiRule) {
        New-NetFirewallRule -DisplayName "Epstein Dashboard API" -Direction Inbound -Port 5000 -Protocol TCP -Action Allow | Out-Null
        Write-Success "Created firewall rule for API (port 5000)"
    } else {
        Write-Success "Firewall rule exists for API"
    }

    $frontendRule = Get-NetFirewallRule -DisplayName "Epstein Dashboard Frontend" -ErrorAction SilentlyContinue
    if (-not $frontendRule) {
        New-NetFirewallRule -DisplayName "Epstein Dashboard Frontend" -Direction Inbound -Port 5173 -Protocol TCP -Action Allow | Out-Null
        Write-Success "Created firewall rule for Frontend (port 5173)"
    } else {
        Write-Success "Firewall rule exists for Frontend"
    }
}

# ============================================================================
# Phase 10: Create Startup Scripts
# ============================================================================

if (-not $UpdatePathsOnly) {
    Write-Step "Phase 10: Creating Startup Scripts"

    # Start backend script
    $startBackend = @"
@echo off
cd /d C:\EpsteinDashboard\dashboard\backend
dotnet run --project src\EpsteinDashboard.Api -c Release
pause
"@
    $startBackend | Out-File -FilePath "$AppPath\start-backend.bat" -Encoding ASCII
    Write-Success "Created: start-backend.bat"

    # Start frontend script
    $startFrontend = @"
@echo off
cd /d C:\EpsteinDashboard\dashboard\frontend
npm run dev -- --host
pause
"@
    $startFrontend | Out-File -FilePath "$AppPath\start-frontend.bat" -Encoding ASCII
    Write-Success "Created: start-frontend.bat"

    # Start all script
    $startAll = @"
@echo off
echo Starting Epstein Dashboard...
start "Backend" cmd /c "C:\EpsteinDashboard\start-backend.bat"
timeout /t 10
start "Frontend" cmd /c "C:\EpsteinDashboard\start-frontend.bat"
echo.
echo Dashboard starting...
echo   Frontend: http://192.168.12.126:5173
echo   API:      http://192.168.12.126:5000
echo   Swagger:  http://192.168.12.126:5000/swagger
"@
    $startAll | Out-File -FilePath "$AppPath\start-dashboard.bat" -Encoding ASCII
    Write-Success "Created: start-dashboard.bat"
}

# ============================================================================
# Complete
# ============================================================================

Write-Step "Migration Complete!"

Write-Host @"

Directory Structure:
  Application: $AppPath
  Data:        $DataPath
  Files:       $FilesPath

To start the dashboard:
  1. Double-click: $AppPath\start-dashboard.bat

  Or manually:
  - Backend:  cd $AppPath\dashboard\backend && dotnet run --project src\EpsteinDashboard.Api -c Release
  - Frontend: cd $AppPath\dashboard\frontend && npm run dev -- --host

Access URLs:
  Frontend: http://192.168.12.126:5173 or http://BobbyHomeEP:5173
  API:      http://192.168.12.126:5000 or http://BobbyHomeEP:5000
  Swagger:  http://192.168.12.126:5000/swagger

Next Steps:
  1. Add your OpenAI API key to: $AppPath\dashboard\backend\appsettings.Local.json
  2. Verify document files are in: $FilesPath
  3. Test the application
  4. (Optional) Set up as Windows Service for auto-start

"@ -ForegroundColor Green
