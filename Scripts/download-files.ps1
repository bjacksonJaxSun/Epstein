# Epstein Dashboard - Download Document Files
# Downloads all ~103 GB of document files (PDFs, images, videos) from Azure Blob Storage

param(
    [string]$DestPath = "D:\Personal\Epstein\data\files",
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
Write-Host "║         EPSTEIN DASHBOARD - DOWNLOAD FILES                   ║" -ForegroundColor Magenta
Write-Host "║                                                              ║" -ForegroundColor Magenta
Write-Host "║   Downloading ~103 GB of documents from Azure Storage        ║" -ForegroundColor Magenta
Write-Host "║                                                              ║" -ForegroundColor Magenta
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host ""
Write-Host "  Destination: $DestPath" -ForegroundColor Gray
if ($Overwrite) {
    Write-Host "  Mode:        Overwrite (re-downloading all files)" -ForegroundColor Gray
} else {
    Write-Host "  Mode:        Default (skipping already-downloaded files)" -ForegroundColor Gray
}

# Configuration
$StorageAccount = "epsteinstorage2024"
$Container = "epstein-files"

# ============================================================
# STEP 1: Check Prerequisites
# ============================================================
Write-Step "1/3" "Checking Prerequisites"

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
# STEP 2: Azure Login & SAS Token
# ============================================================
Write-Step "2/3" "Azure Authentication & Access Token"

Write-Progress-Status "Checking Azure login status..."
$loginStatus = az account show 2>$null | ConvertFrom-Json -ErrorAction SilentlyContinue
if (-not $loginStatus) {
    Write-Progress-Status "Opening browser for Azure login..."
    az login
    $loginStatus = az account show | ConvertFrom-Json
}
Write-Success "Logged in as: $($loginStatus.user.name)"
Write-Success "Subscription: $($loginStatus.name)"

Write-Host ""
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
# STEP 3: Download Document Files
# ============================================================
Write-Step "3/3" "Downloading Document Files"

New-Item -ItemType Directory -Force -Path $DestPath | Out-Null

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
Write-Host "  Destination: $DestPath" -ForegroundColor Gray
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
    $localFolder = "$DestPath\$folderName"
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
    azcopy copy "https://$StorageAccount.blob.core.windows.net/$Container/VOL00010/VOL00010/$folderName/?$sasToken" "$localFolder\" --recursive --overwrite=$overwriteMode
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
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                                                              ║" -ForegroundColor Green
Write-Host "║                    DOWNLOAD COMPLETE!                        ║" -ForegroundColor Green
Write-Host "║                                                              ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Success "All $totalFolders folders complete  |  Total time: ${totalMins}m ${totalSecs}s"
Write-Host ""
Write-Host "  Files downloaded to: $DestPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Docker volume mapping:" -ForegroundColor Gray
Write-Host "    $DestPath" -ForegroundColor White
Write-Host "    -> /data/VOL00010/VOL00010  (inside container, read-only)" -ForegroundColor DarkGray
Write-Host ""
