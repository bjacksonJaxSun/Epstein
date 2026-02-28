# Epstein Dashboard - Local Restore Script
# Run this on BobbyHomeEP to restore from Azure Storage

param(
    [string]$InstallPath = "D:\Personal\Epstein",
    [string]$DataPath = "D:\Personal\Epstein\data",
    [switch]$SkipFiles,
    [switch]$Overwrite
)

$ErrorActionPreference = "Continue"

function Write-Step {
    param([string]$Step, [string]$Message)
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host "  [$Step] $Message" -ForegroundColor Yellow
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
}

function Write-Progress-Status {
    param([string]$Status)
    Write-Host "  → $Status" -ForegroundColor White
}

function Write-Success {
    param([string]$Message)
    Write-Host "  ✓ $Message" -ForegroundColor Green
}

function Write-Error-Message {
    param([string]$Message)
    Write-Host "  ✗ $Message" -ForegroundColor Red
}

Clear-Host
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "║                                                              ║" -ForegroundColor Magenta
Write-Host "║         EPSTEIN DASHBOARD - LOCAL RESTORE                    ║" -ForegroundColor Magenta
Write-Host "║                                                              ║" -ForegroundColor Magenta
Write-Host "║   Restoring from Azure Storage to local machine              ║" -ForegroundColor Magenta
Write-Host "║                                                              ║" -ForegroundColor Magenta
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host ""
Write-Host "  Install Path: $InstallPath" -ForegroundColor Gray
Write-Host "  Data Path:    $DataPath" -ForegroundColor Gray
if ($SkipFiles) {
    Write-Host "  Mode:         Databases only (-SkipFiles)" -ForegroundColor Gray
} elseif ($Overwrite) {
    Write-Host "  Mode:         Overwrite (re-downloading all files)" -ForegroundColor Gray
} else {
    Write-Host "  Mode:         Default (skipping already-downloaded files)" -ForegroundColor Gray
}

# Configuration
$StorageAccount = "epsteinstorage2024"
$ACR = "epsteinregistry.azurecr.io"

# ============================================================
# STEP 1: Check Prerequisites
# ============================================================
Write-Step "1/7" "Checking Prerequisites"

Write-Progress-Status "Checking Azure CLI..."
# Add the standard Azure CLI install location to PATH if not already present
$azCliPath = "C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin"
if ((Test-Path $azCliPath) -and ($env:PATH -notlike "*$azCliPath*")) {
    $env:PATH = "$azCliPath;$env:PATH"
}
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Error-Message "Azure CLI is not installed!"
    Write-Host ""
    Write-Host "  Please install Azure CLI first:" -ForegroundColor Yellow
    Write-Host "  https://docs.microsoft.com/en-us/cli/azure/install-azure-cli-windows" -ForegroundColor Cyan
    exit 1
}
$azVersion = (az version --output json | ConvertFrom-Json).'azure-cli'
Write-Success "Azure CLI: $azVersion"

Write-Progress-Status "Checking azcopy..."
if (-not (Get-Command azcopy -ErrorAction SilentlyContinue)) {
    Write-Progress-Status "Installing azcopy..."
    try {
        Invoke-WebRequest -Uri "https://aka.ms/downloadazcopy-v10-windows" -OutFile "$env:TEMP\azcopy.zip"
        Expand-Archive -Path "$env:TEMP\azcopy.zip" -DestinationPath "$env:TEMP\azcopy" -Force
        $azcopyExe = Get-ChildItem -Path "$env:TEMP\azcopy" -Recurse -Filter "azcopy.exe" | Select-Object -First 1
        Copy-Item $azcopyExe.FullName -Destination "C:\Windows\System32\azcopy.exe"
        Write-Success "azcopy installed"
    } catch {
        Write-Error-Message "Failed to install azcopy. Please install manually."
        exit 1
    }
} else {
    Write-Success "azcopy: installed"
}

# ============================================================
# STEP 2: Create Directories
# ============================================================
Write-Step "2/7" "Creating Data Directories"

Write-Progress-Status "Creating $DataPath\database..."
New-Item -ItemType Directory -Force -Path "$DataPath\database" | Out-Null
Write-Success "Created database directory"

Write-Progress-Status "Creating $DataPath\postgres..."
New-Item -ItemType Directory -Force -Path "$DataPath\postgres" | Out-Null
Write-Success "Created postgres directory"

Write-Progress-Status "Creating $DataPath\files..."
New-Item -ItemType Directory -Force -Path "$DataPath\files" | Out-Null
Write-Success "Created files directory"

# ============================================================
# STEP 3: Azure Login
# ============================================================
Write-Step "3/7" "Azure Authentication"

Write-Progress-Status "Checking Azure login status..."
$loginStatus = az account show 2>$null | ConvertFrom-Json -ErrorAction SilentlyContinue
if (-not $loginStatus) {
    Write-Progress-Status "Opening browser for Azure login..."
    az login
    $loginStatus = az account show | ConvertFrom-Json
}
Write-Success "Logged in as: $($loginStatus.user.name)"
Write-Success "Subscription: $($loginStatus.name)"

# ============================================================
# STEP 4: Generate SAS Token
# ============================================================
Write-Step "4/7" "Generating Storage Access Token"

Write-Progress-Status "Generating SAS token for storage account..."
$expiry = (Get-Date).AddDays(7).ToString("yyyy-MM-ddTHH:mmZ")
$sasToken = az storage account generate-sas `
    --account-name $StorageAccount `
    --permissions rl `
    --services b `
    --resource-types sco `
    --expiry $expiry `
    --output tsv 2>$null

if (-not $sasToken) {
    Write-Error-Message "Failed to generate SAS token!"
    Write-Host "  Make sure you have access to storage account: $StorageAccount" -ForegroundColor Yellow
    exit 1
}
Write-Success "SAS token generated (expires in 7 days)"

# ============================================================
# STEP 5: Download Databases
# ============================================================
Write-Step "5/7" "Downloading Databases from Azure"

Write-Host ""
Write-Host "  ┌────────────────────────────────────────────────────────┐" -ForegroundColor Gray
Write-Host "  │  Downloading PostgreSQL dump (2.4 GB)                  │" -ForegroundColor Gray
Write-Host "  │  This will take several minutes...                    │" -ForegroundColor Gray
Write-Host "  └────────────────────────────────────────────────────────┘" -ForegroundColor Gray
Write-Host ""

$startTime = Get-Date
azcopy copy "https://$StorageAccount.blob.core.windows.net/epstein-files/database/epstein_db_export.dump?$sasToken" "$DataPath\database\" --overwrite=true
$elapsed = (Get-Date) - $startTime
Write-Success "PostgreSQL dump downloaded in $([math]::Round($elapsed.TotalMinutes, 1)) minutes"

Write-Host ""
Write-Host "  ┌────────────────────────────────────────────────────────┐" -ForegroundColor Gray
Write-Host "  │  Downloading SQLite database (2.2 GB)                  │" -ForegroundColor Gray
Write-Host "  │  This will take several minutes...                    │" -ForegroundColor Gray
Write-Host "  └────────────────────────────────────────────────────────┘" -ForegroundColor Gray
Write-Host ""

$startTime = Get-Date
azcopy copy "https://$StorageAccount.blob.core.windows.net/epstein-files/database/epstein_documents.db?$sasToken" "$DataPath\" --overwrite=true
$elapsed = (Get-Date) - $startTime
Write-Success "SQLite database downloaded in $([math]::Round($elapsed.TotalMinutes, 1)) minutes"

# Verify downloads
$pgDump = Get-Item "$DataPath\database\epstein_db_export.dump" -ErrorAction SilentlyContinue
$sqliteDb = Get-Item "$DataPath\epstein_documents.db" -ErrorAction SilentlyContinue

if ($pgDump -and $sqliteDb) {
    Write-Host ""
    Write-Host "  Downloaded files:" -ForegroundColor Cyan
    Write-Host "    PostgreSQL: $([math]::Round($pgDump.Length / 1GB, 2)) GB" -ForegroundColor White
    Write-Host "    SQLite:     $([math]::Round($sqliteDb.Length / 1GB, 2)) GB" -ForegroundColor White
} else {
    Write-Error-Message "Download verification failed!"
    exit 1
}

# ============================================================
# STEP 6: Download Document Files
# ============================================================
Write-Step "6/7" "Downloading Document Files from Azure"

if ($SkipFiles) {
    Write-Host "  ⚠ Skipping document file download (-SkipFiles flag set)" -ForegroundColor Yellow
    Write-Host "  Files must be present at: $DataPath\files" -ForegroundColor Gray
} else {
    # Already-downloaded files are skipped by default; use -Overwrite to force re-download
    $overwriteMode = if ($Overwrite) { "true" } else { "false" }

    # Folders ordered smallest-first for quick early wins; DataSet_10 is the big one at the end
    $folders = @(
        @{Name="DataSet_6";  Files=15;     SizeLabel="54 MB"},
        @{Name="DataSet_5";  Files=122;    SizeLabel="62 MB"},
        @{Name="DataSet_7";  Files=19;     SizeLabel="99 MB"},
        @{Name="DataSet_12"; Files=152;    SizeLabel="121 MB"},
        @{Name="DataSet_4";  Files=154;    SizeLabel="359 MB"},
        @{Name="DataSet_3";  Files=69;     SizeLabel="599 MB"},
        @{Name="DataSet_2";  Files=577;    SizeLabel="633 MB"},
        @{Name="DataSet_1";  Files=3158;   SizeLabel="1.3 GB"},
        @{Name="DataSet_11"; Files=49874;  SizeLabel="4.6 GB"},
        @{Name="NATIVES";    Files=872;    SizeLabel="6.0 GB"},
        @{Name="DataSet_9";  Files=55926;  SizeLabel="8.5 GB"},
        @{Name="DataSet_8";  Files=13639;  SizeLabel="12 GB"},
        @{Name="DataSet_10"; Files=503152; SizeLabel="69 GB"}
    )

    $totalFolders = $folders.Count
    $overallStart = Get-Date
    $completedFolders = 0

    Write-Host ""
    Write-Host "  Destination: $DataPath\files" -ForegroundColor Gray
    Write-Host "  Total:       ~103 GB across 627,729 files in $totalFolders dataset folders" -ForegroundColor Gray
    if ($Overwrite) {
        Write-Host "  ⚠ Overwrite mode: all files will be re-downloaded" -ForegroundColor Yellow
    } else {
        Write-Host "  Already-downloaded files will be skipped automatically" -ForegroundColor Gray
    }
    Write-Host ""

    foreach ($folder in $folders) {
        $completedFolders++
        $folderName = $folder.Name
        $localFolder = "$DataPath\files\$folderName"
        $overallElapsed = (Get-Date) - $overallStart
        $overallMins = [math]::Floor($overallElapsed.TotalMinutes)
        $overallSecs = $overallElapsed.Seconds

        Write-Host "  ────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
        Write-Host "  [$completedFolders/$totalFolders] $folderName" -ForegroundColor Cyan -NoNewline
        Write-Host "  ($($folder.Files.ToString('N0')) files, $($folder.SizeLabel))" -ForegroundColor Gray -NoNewline
        Write-Host "  |  overall: ${overallMins}m ${overallSecs}s" -ForegroundColor DarkGray
        Write-Host ""

        New-Item -ItemType Directory -Force -Path $localFolder | Out-Null

        $folderStart = Get-Date
        azcopy copy "https://$StorageAccount.blob.core.windows.net/epstein-files/VOL00010/VOL00010/$folderName/?$sasToken" "$localFolder\" --recursive --overwrite=$overwriteMode
        $folderElapsed = (Get-Date) - $folderStart
        $folderMins = [math]::Floor($folderElapsed.TotalMinutes)
        $folderSecs = $folderElapsed.Seconds

        Write-Host ""
        Write-Success "$folderName done in ${folderMins}m ${folderSecs}s"
    }

    $totalElapsed = (Get-Date) - $overallStart
    $totalMins = [math]::Floor($totalElapsed.TotalMinutes)
    $totalSecs = $totalElapsed.Seconds

    Write-Host ""
    Write-Host "  ────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
    Write-Success "All $totalFolders folders complete  |  Total time: ${totalMins}m ${totalSecs}s"
}

# ============================================================
# STEP 7: Create Configuration Files
# ============================================================
Write-Step "7/7" "Creating Configuration Files"

# Create .env file
$envContent = @"
# Epstein Dashboard Environment Configuration
# Generated on $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

# PostgreSQL
POSTGRES_USER=epstein_user
POSTGRES_PASSWORD=epstein_secure_pw_2024
POSTGRES_DB=epstein_documents

# OpenAI API Key (required for AI features)
# Get your key from: https://platform.openai.com/api-keys
OPENAI_API_KEY=

# JWT Authentication
JWT_SECRET=epstein-dashboard-jwt-secret-change-in-production-32chars
JWT_ISSUER=EpsteinDashboard
JWT_AUDIENCE=EpsteinDashboardUsers

# Azure Storage (for serving files)
AZURE_STORAGE_ACCOUNT=$StorageAccount
"@

$envPath = "$InstallPath\.env"
if (-not (Test-Path $envPath)) {
    $envContent | Out-File -FilePath $envPath -Encoding utf8 -NoNewline
    Write-Success "Created .env file"
    Write-Host "    ⚠ IMPORTANT: Edit .env and add your OPENAI_API_KEY" -ForegroundColor Yellow
} else {
    Write-Progress-Status ".env file already exists, skipping"
}

# Create docker-compose.local.yml
Write-Progress-Status "Creating docker-compose.local.yml..."

$composeContent = @"
version: '3.8'

services:
  postgres:
    image: epsteinregistry.azurecr.io/epstein-postgres:latest
    container_name: epstein-postgres
    restart: unless-stopped
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
      - ./data/database:/docker-entrypoint-initdb.d:ro
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: `${POSTGRES_USER:-epstein_user}
      POSTGRES_PASSWORD: `${POSTGRES_PASSWORD:-epstein_secure_pw_2024}
      POSTGRES_DB: `${POSTGRES_DB:-epstein_documents}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U epstein_user -d epstein_documents"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 120s
    networks:
      - epstein-network

  python:
    image: epsteinregistry.azurecr.io/epstein-python:latest
    container_name: epstein-python
    restart: unless-stopped
    ports:
      - "5050:5050"
      - "5051:5051"
    environment:
      DATABASE_URL: postgresql://`${POSTGRES_USER:-epstein_user}:`${POSTGRES_PASSWORD:-epstein_secure_pw_2024}@postgres:5432/`${POSTGRES_DB:-epstein_documents}
      PYTHONUNBUFFERED: 1
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - epstein-network

  api:
    image: epsteinregistry.azurecr.io/epstein-api:latest
    container_name: epstein-api
    restart: unless-stopped
    ports:
      - "5203:5203"
    volumes:
      - ./data/epstein_documents.db:/data/epstein_documents.db
      - ./data/files:/data/VOL00010/VOL00010:ro
    environment:
      ConnectionStrings__PostgresDb: "Host=postgres;Database=`${POSTGRES_DB:-epstein_documents};Username=`${POSTGRES_USER:-epstein_user};Password=`${POSTGRES_PASSWORD:-epstein_secure_pw_2024}"
      ConnectionStrings__EpsteinDb: "Data Source=/data/epstein_documents.db"
      Embedding__ServiceUrl: "http://python:5050"
      Reranking__ServiceUrl: "http://python:5051"
      OpenAI__ApiKey: `${OPENAI_API_KEY}
      Jwt__Secret: `${JWT_SECRET}
      Jwt__Issuer: `${JWT_ISSUER:-EpsteinDashboard}
      Jwt__Audience: `${JWT_AUDIENCE:-EpsteinDashboardUsers}
    depends_on:
      postgres:
        condition: service_healthy
      python:
        condition: service_started
    networks:
      - epstein-network

  frontend:
    image: epsteinregistry.azurecr.io/epstein-frontend:latest
    container_name: epstein-frontend
    restart: unless-stopped
    ports:
      - "80:80"
    depends_on:
      - api
    networks:
      - epstein-network

networks:
  epstein-network:
    driver: bridge
"@

$composeContent | Out-File -FilePath "$InstallPath\docker-compose.local.yml" -Encoding utf8 -NoNewline
Write-Success "Created docker-compose.local.yml"

# ============================================================
# COMPLETE
# ============================================================
Write-Host ""
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                                                              ║" -ForegroundColor Green
Write-Host "║                    RESTORE COMPLETE!                         ║" -ForegroundColor Green
Write-Host "║                                                              ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  Downloaded Data:" -ForegroundColor Cyan
Write-Host "  ────────────────────────────────────────────────────────────"
Write-Host "    PostgreSQL dump: $DataPath\database\epstein_db_export.dump"
Write-Host "    SQLite database: $DataPath\epstein_documents.db"
if (-not $SkipFiles) {
Write-Host "    Document files:  $DataPath\files  (PDFs, images, videos)"
}
Write-Host ""
Write-Host ""
Write-Host "  ┌────────────────────────────────────────────────────────────┐" -ForegroundColor Yellow
Write-Host "  │                      NEXT STEPS                            │" -ForegroundColor Yellow
Write-Host "  └────────────────────────────────────────────────────────────┘" -ForegroundColor Yellow
Write-Host ""
Write-Host "  1. Install Docker Desktop and pull images:" -ForegroundColor White
Write-Host "     az acr login --name epsteinregistry" -ForegroundColor Cyan
Write-Host "     docker pull $ACR/epstein-postgres:latest" -ForegroundColor Cyan
Write-Host "     docker pull $ACR/epstein-python:latest" -ForegroundColor Cyan
Write-Host "     docker pull $ACR/epstein-api:latest" -ForegroundColor Cyan
Write-Host "     docker pull $ACR/epstein-frontend:latest" -ForegroundColor Cyan
Write-Host ""
Write-Host "  2. Edit .env and add your OPENAI_API_KEY:" -ForegroundColor White
Write-Host "     notepad $InstallPath\.env" -ForegroundColor Cyan
Write-Host ""
Write-Host "  3. Start the application:" -ForegroundColor White
Write-Host "     cd $InstallPath" -ForegroundColor Cyan
Write-Host "     docker-compose -f docker-compose.local.yml up -d" -ForegroundColor Cyan
Write-Host ""
Write-Host "  4. Wait for PostgreSQL to restore (~5-10 minutes):" -ForegroundColor White
Write-Host "     docker logs -f epstein-postgres" -ForegroundColor Cyan
Write-Host ""
Write-Host "  5. Access the dashboard:" -ForegroundColor White
Write-Host "     URL:      http://localhost" -ForegroundColor Cyan
Write-Host "     Login:    admin" -ForegroundColor Cyan
Write-Host "     Password: Admin123" -ForegroundColor Cyan
Write-Host ""
Write-Host "  ────────────────────────────────────────────────────────────"
Write-Host ""
