# ============================================================================
# Copy Files from Azure VM to BobbyHomeEP
# Run this script on BobbyHomeEP as Administrator
# ============================================================================

param(
    [string]$VMHost = "20.25.96.123",
    [string]$VMUser = "azureuser",
    [string]$DestinationPath = "D:\EpsteinData\epstein_files",
    [switch]$DatabaseOnly,
    [switch]$FilesOnly,
    [switch]$Resume
)

$ErrorActionPreference = "Stop"

# SSH key path
$SSHKey = "$env:USERPROFILE\.ssh\azure_vm"

# Source path on VM
$VMSourcePath = "/data/VOL00010/VOL00010"
$VMDbPassword = "epstein_secure_pw_2024"

# ============================================================================
# Folder Information (with SizeBytes for accurate progress tracking)
# ============================================================================

$TotalSizeBytes = 103L * 1024 * 1024 * 1024  # ~103 GB total
$TotalExpectedFiles = 627729

# ============================================================================
# Helper Functions
# ============================================================================

function Write-Step {
    param([string]$Message)
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host $Message -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
}

function Format-Size {
    param([long]$Bytes)
    if ($Bytes -ge 1GB) { return "{0:N2} GB" -f ($Bytes / 1GB) }
    elseif ($Bytes -ge 1MB) { return "{0:N1} MB" -f ($Bytes / 1MB) }
    elseif ($Bytes -ge 1KB) { return "{0:N1} KB" -f ($Bytes / 1KB) }
    else { return "$Bytes B" }
}

function Format-Speed {
    param([double]$BytesPerSecond)
    if ($BytesPerSecond -ge 1GB) { return "{0:N1} GB/s" -f ($BytesPerSecond / 1GB) }
    elseif ($BytesPerSecond -ge 1MB) { return "{0:N1} MB/s" -f ($BytesPerSecond / 1MB) }
    elseif ($BytesPerSecond -ge 1KB) { return "{0:N1} KB/s" -f ($BytesPerSecond / 1KB) }
    else { return "{0:N0} B/s" -f $BytesPerSecond }
}

function Format-Duration {
    param([TimeSpan]$Duration)
    if ($Duration.TotalHours -ge 1) {
        return "{0}h {1:D2}m {2:D2}s" -f [int][math]::Floor($Duration.TotalHours), $Duration.Minutes, $Duration.Seconds
    } elseif ($Duration.TotalMinutes -ge 1) {
        return "{0}m {1:D2}s" -f [int][math]::Floor($Duration.TotalMinutes), $Duration.Seconds
    } else {
        return "{0}s" -f [int]$Duration.TotalSeconds
    }
}

function Write-ProgressBar {
    param(
        [double]$Percent,
        [int]$Width = 40
    )
    $filled = [int]($Percent / 100 * $Width)
    $empty = $Width - $filled
    $bar = ("█" * $filled) + ("░" * $empty)
    return "[$bar] {0:N1}%" -f $Percent
}

function Get-FolderSize {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return 0 }
    $size = (Get-ChildItem $Path -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    if ($null -eq $size) { return 0 }
    return [long]$size
}

function Get-FolderFileCount {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return 0 }
    return (Get-ChildItem $Path -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
}

function Write-StatusLine {
    param(
        [string]$FolderName,
        [int]$FolderNum,
        [int]$TotalFolders,
        [long]$BytesDownloaded,
        [long]$TotalBytes,
        [int]$FilesDownloaded,
        [int]$TotalFiles,
        [TimeSpan]$Elapsed,
        [double]$SpeedBps
    )
    $pct = if ($TotalBytes -gt 0) { ($BytesDownloaded / $TotalBytes) * 100 } else { 0 }
    $bar = Write-ProgressBar -Percent $pct
    $sizeStr = "$(Format-Size $BytesDownloaded) / $(Format-Size $TotalBytes)"
    $speedStr = if ($SpeedBps -gt 0) { Format-Speed $SpeedBps } else { "-- MB/s" }
    $etaStr = if ($SpeedBps -gt 0 -and $BytesDownloaded -lt $TotalBytes) {
        $remainBytes = $TotalBytes - $BytesDownloaded
        $etaSec = $remainBytes / $SpeedBps
        Format-Duration ([TimeSpan]::FromSeconds($etaSec))
    } else { "--" }

    Write-Host ""
    Write-Host "  Overall  $bar" -ForegroundColor White
    Write-Host "  Size     $sizeStr    Speed: $speedStr    ETA: $etaStr" -ForegroundColor Gray
    Write-Host "  Files    $FilesDownloaded / $TotalFiles    Folders: $FolderNum / $TotalFolders    Elapsed: $(Format-Duration $Elapsed)" -ForegroundColor Gray
}

# ============================================================================
# Check Prerequisites
# ============================================================================

Write-Step "Checking Prerequisites"

# Check SSH
if (-not (Get-Command ssh -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] SSH not found. Please install OpenSSH." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] SSH available" -ForegroundColor Green

# Check SCP
if (-not (Get-Command scp -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] SCP not found. Please install OpenSSH." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] SCP available" -ForegroundColor Green

# Test VM connection via SSH (ICMP ping is blocked on Azure VMs)
Write-Host "Testing SSH connection to $VMHost..."
ssh -i $SSHKey -o ConnectTimeout=10 -o BatchMode=yes "${VMUser}@${VMHost}" "echo ok" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Cannot SSH to ${VMUser}@${VMHost}" -ForegroundColor Red
    Write-Host "        Check that the VM is running and your SSH key is configured." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] VM is reachable via SSH" -ForegroundColor Green

# Create destination directory
if (-not (Test-Path $DestinationPath)) {
    New-Item -ItemType Directory -Force -Path $DestinationPath | Out-Null
    Write-Host "[OK] Created: $DestinationPath" -ForegroundColor Green
} else {
    Write-Host "[OK] Destination exists: $DestinationPath" -ForegroundColor Green
}

# Check destination disk space
$drive = (Get-Item $DestinationPath).PSDrive
$freeSpace = (Get-PSDrive $drive.Name).Free
Write-Host "[INFO] Free disk space on $($drive.Name):\  $(Format-Size $freeSpace)" -ForegroundColor $(if ($freeSpace -lt 110GB) { "Yellow" } else { "Green" })
if ($freeSpace -lt 110GB) {
    Write-Host "[WARN] Less than 110 GB free - you may run out of space during download!" -ForegroundColor Yellow
}

# Create backups directory
$BackupsPath = "D:\EpsteinData\backups"
if (-not (Test-Path $BackupsPath)) {
    New-Item -ItemType Directory -Force -Path $BackupsPath | Out-Null
}

# ============================================================================
# Download Database Backup
# ============================================================================

if (-not $FilesOnly) {
    Write-Step "Downloading Database Backup (6.1 GB)"

    $dumpFile = "$BackupsPath\epstein_backup.dump"

    if ((Test-Path $dumpFile) -and $Resume) {
        $existingSize = Format-Size (Get-Item $dumpFile).Length
        Write-Host "[SKIP] Database dump already exists: $dumpFile ($existingSize)" -ForegroundColor Yellow
    } else {
        Write-Host "Creating database dump on VM..."

        # Create dump on VM
        $dbStart = Get-Date
        ssh -i $SSHKey "${VMUser}@${VMHost}" "PGPASSWORD=$VMDbPassword pg_dump -h localhost -U epstein_user -d epstein_documents -F c -f /tmp/epstein_backup.dump"

        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] Failed to create database dump" -ForegroundColor Red
            exit 1
        }
        $dbDumpTime = (Get-Date) - $dbStart
        Write-Host "[OK] Database dump created on VM ($(Format-Duration $dbDumpTime))" -ForegroundColor Green

        Write-Host "Downloading database dump..."
        $dbDownloadStart = Get-Date
        scp -i $SSHKey "${VMUser}@${VMHost}:/tmp/epstein_backup.dump" $dumpFile

        if (Test-Path $dumpFile) {
            $fileSize = (Get-Item $dumpFile).Length
            $dbDownloadTime = (Get-Date) - $dbDownloadStart
            $dbSpeed = if ($dbDownloadTime.TotalSeconds -gt 0) { $fileSize / $dbDownloadTime.TotalSeconds } else { 0 }
            Write-Host "[OK] Database dump downloaded: $(Format-Size $fileSize) in $(Format-Duration $dbDownloadTime) ($(Format-Speed $dbSpeed))" -ForegroundColor Green
        } else {
            Write-Host "[ERROR] Failed to download database dump" -ForegroundColor Red
            exit 1
        }
    }
}

# ============================================================================
# Download Document Files
# ============================================================================

if (-not $DatabaseOnly) {
    Write-Step "Downloading Document Files (102 GB)"

    Write-Host @"

This will download 627,729 files (102 GB) from the Azure VM.
Estimated time: 2-4 hours depending on network speed.

  Folder        Files       Size       Order
  ----------    ---------   --------   -----
  DataSet_6     15          54 MB      1/13
  DataSet_5     122         62 MB      2/13
  DataSet_7     19          99 MB      3/13
  DataSet_12    152         121 MB     4/13
  DataSet_4     154         359 MB     5/13
  DataSet_3     69          599 MB     6/13
  DataSet_2     577         633 MB     7/13
  DataSet_1     3,158       1.3 GB     8/13
  DataSet_11    49,874      4.6 GB     9/13
  NATIVES       872         6.0 GB     10/13
  DataSet_9     55,926      8.5 GB     11/13
  DataSet_8     13,639      12 GB      12/13
  DataSet_10    503,152     69 GB      13/13
  ----------    ---------   --------
  TOTAL         627,729     102 GB

"@ -ForegroundColor Yellow

    $continue = Read-Host "Continue? (Y/N)"
    if ($continue -ne "Y" -and $continue -ne "y") {
        Write-Host "Aborted by user." -ForegroundColor Yellow
        exit 0
    }

    # Define folders in order (smallest first for quick wins, largest last)
    # SizeBytes used for accurate progress/ETA calculation
    $folders = @(
        @{Name="DataSet_6";  Files=15;     SizeBytes=54MB;   SizeLabel="54 MB"},
        @{Name="DataSet_5";  Files=122;    SizeBytes=62MB;   SizeLabel="62 MB"},
        @{Name="DataSet_7";  Files=19;     SizeBytes=99MB;   SizeLabel="99 MB"},
        @{Name="DataSet_12"; Files=152;    SizeBytes=121MB;  SizeLabel="121 MB"},
        @{Name="DataSet_4";  Files=154;    SizeBytes=359MB;  SizeLabel="359 MB"},
        @{Name="DataSet_3";  Files=69;     SizeBytes=599MB;  SizeLabel="599 MB"},
        @{Name="DataSet_2";  Files=577;    SizeBytes=633MB;  SizeLabel="633 MB"},
        @{Name="DataSet_1";  Files=3158;   SizeBytes=1.3GB;  SizeLabel="1.3 GB"},
        @{Name="DataSet_11"; Files=49874;  SizeBytes=4.6GB;  SizeLabel="4.6 GB"},
        @{Name="NATIVES";    Files=872;    SizeBytes=6.0GB;  SizeLabel="6.0 GB"},
        @{Name="DataSet_9";  Files=55926;  SizeBytes=8.5GB;  SizeLabel="8.5 GB"},
        @{Name="DataSet_8";  Files=13639;  SizeBytes=12GB;   SizeLabel="12 GB"},
        @{Name="DataSet_10"; Files=503152; SizeBytes=69GB;   SizeLabel="69 GB"}
    )

    $totalFolders = $folders.Count
    $completedFolders = 0
    $cumulativeBytesDownloaded = 0L
    $cumulativeFilesDownloaded = 0
    $cumulativeBytesExpected = 0L
    $folders | ForEach-Object { $cumulativeBytesExpected += $_.SizeBytes }
    $startTime = Get-Date
    $folderTimings = @()

    Write-Host ""
    Write-Host "  Starting download at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor White
    Write-Host "  ================================================================" -ForegroundColor DarkGray

    foreach ($folder in $folders) {
        $folderName = $folder.Name
        $folderDest = Join-Path $DestinationPath $folderName
        $folderNum = $completedFolders + 1

        # Check if folder already exists and has files (for resume)
        if ($Resume -and (Test-Path $folderDest)) {
            $existingFiles = Get-FolderFileCount $folderDest
            if ($existingFiles -ge $folder.Files * 0.95) {  # 95% threshold
                $existingSize = Get-FolderSize $folderDest
                $cumulativeBytesDownloaded += $existingSize
                $cumulativeFilesDownloaded += $existingFiles
                $completedFolders++
                Write-Host ""
                Write-Host "  [$folderNum/$totalFolders] $folderName" -ForegroundColor Yellow -NoNewline
                Write-Host "  SKIPPED (already has $existingFiles/$($folder.Files) files, $(Format-Size $existingSize))" -ForegroundColor Yellow
                continue
            }
        }

        # Folder header
        Write-Host ""
        Write-Host "  ----------------------------------------------------------------" -ForegroundColor DarkGray
        Write-Host "  [$folderNum/$totalFolders] $folderName" -ForegroundColor Cyan -NoNewline
        Write-Host "  ($($folder.Files.ToString('N0')) files, $($folder.SizeLabel))" -ForegroundColor Gray
        Write-Host "  Started: $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor DarkGray

        # Create destination folder
        if (-not (Test-Path $folderDest)) {
            New-Item -ItemType Directory -Force -Path $folderDest | Out-Null
        }

        # Use SCP to copy folder
        $sourcePath = "${VMUser}@${VMHost}:${VMSourcePath}/${folderName}/*"
        $folderStart = Get-Date

        # SCP with recursive copy
        scp -i $SSHKey -r $sourcePath "$folderDest\"
        $scpExitCode = $LASTEXITCODE

        $folderEnd = Get-Date
        $folderDuration = $folderEnd - $folderStart

        # Measure actual downloaded size and file count
        $actualSize = Get-FolderSize $folderDest
        $actualFiles = Get-FolderFileCount $folderDest
        $folderSpeed = if ($folderDuration.TotalSeconds -gt 0) { $actualSize / $folderDuration.TotalSeconds } else { 0 }

        $cumulativeBytesDownloaded += $actualSize
        $cumulativeFilesDownloaded += $actualFiles
        $completedFolders++

        # Folder result
        if ($scpExitCode -eq 0) {
            Write-Host "  OK " -ForegroundColor Green -NoNewline
        } else {
            Write-Host "  WARN " -ForegroundColor Yellow -NoNewline
        }
        Write-Host "$actualFiles/$($folder.Files) files, $(Format-Size $actualSize) in $(Format-Duration $folderDuration) @ $(Format-Speed $folderSpeed)" -ForegroundColor $(if ($scpExitCode -eq 0) { "Green" } else { "Yellow" })

        # Store timing for speed averaging
        $folderTimings += @{ Bytes=$actualSize; Seconds=$folderDuration.TotalSeconds }

        # Calculate overall speed (weighted average from all completed folders)
        $totalTransferBytes = ($folderTimings | Measure-Object -Property Bytes -Sum).Sum
        $totalTransferSecs = ($folderTimings | Measure-Object -Property Seconds -Sum).Sum
        $overallSpeed = if ($totalTransferSecs -gt 0) { $totalTransferBytes / $totalTransferSecs } else { 0 }

        # Overall progress
        $overallElapsed = (Get-Date) - $startTime
        Write-StatusLine `
            -FolderName $folderName `
            -FolderNum $completedFolders `
            -TotalFolders $totalFolders `
            -BytesDownloaded $cumulativeBytesDownloaded `
            -TotalBytes $cumulativeBytesExpected `
            -FilesDownloaded $cumulativeFilesDownloaded `
            -TotalFiles $TotalExpectedFiles `
            -Elapsed $overallElapsed `
            -SpeedBps $overallSpeed
    }

    # ============================================================================
    # Final Summary
    # ============================================================================

    $totalElapsed = (Get-Date) - $startTime
    $avgSpeed = if ($totalElapsed.TotalSeconds -gt 0) { $cumulativeBytesDownloaded / $totalElapsed.TotalSeconds } else { 0 }

    Write-Step "Download Complete"

    Write-Host ""
    Write-Host "  Finished at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor White
    Write-Host ""
    Write-Host "  Total time      $(Format-Duration $totalElapsed)" -ForegroundColor Green
    Write-Host "  Total size      $(Format-Size $cumulativeBytesDownloaded)" -ForegroundColor Green
    Write-Host "  Total files     $($cumulativeFilesDownloaded.ToString('N0'))" -ForegroundColor Green
    Write-Host "  Avg speed       $(Format-Speed $avgSpeed)" -ForegroundColor Green
    Write-Host "  Destination     $DestinationPath" -ForegroundColor Green
    Write-Host ""

    # Verify file counts
    Write-Host "  Verification:" -ForegroundColor Cyan
    Write-Host "  ----------------------------------------------------------------" -ForegroundColor DarkGray

    $totalDownloaded = 0

    foreach ($folder in $folders) {
        $folderDest = Join-Path $DestinationPath $folder.Name
        if (Test-Path $folderDest) {
            $count = Get-FolderFileCount $folderDest
            $totalDownloaded += $count
            $pct = if ($folder.Files -gt 0) { [math]::Round(($count / $folder.Files) * 100, 0) } else { 100 }
            $status = if ($count -ge $folder.Files * 0.95) { "OK  " } else { "WARN" }
            $color = if ($count -ge $folder.Files * 0.95) { "Green" } else { "Yellow" }
            Write-Host "  [$status] $($folder.Name.PadRight(12)) $($count.ToString('N0').PadLeft(9)) / $($folder.Files.ToString('N0').PadLeft(9))  ($pct%)" -ForegroundColor $color
        } else {
            Write-Host "  [MISS] $($folder.Name.PadRight(12))         0 / $($folder.Files.ToString('N0').PadLeft(9))  (0%)" -ForegroundColor Red
        }
    }

    Write-Host "  ----------------------------------------------------------------" -ForegroundColor DarkGray
    $overallPct = [math]::Round(($totalDownloaded / $TotalExpectedFiles) * 100, 1)
    $totalColor = if ($overallPct -ge 95) { "Green" } else { "Yellow" }
    Write-Host "  TOTAL   $($totalDownloaded.ToString('N0').PadLeft(18)) / $($TotalExpectedFiles.ToString('N0').PadLeft(9))  ($overallPct%)" -ForegroundColor $totalColor
    Write-Host ""

    if ($overallPct -ge 95) {
        Write-Host "  [OK] Download successful!" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] Some files may be missing. Run with -Resume to retry." -ForegroundColor Yellow
    }
}

# ============================================================================
# Next Steps
# ============================================================================

Write-Step "Next Steps"

Write-Host @"

Files have been downloaded to: $DestinationPath
Database backup is at: $BackupsPath\epstein_backup.dump

To continue the migration:

1. Install PostgreSQL 16 if not already installed
   Download: https://www.postgresql.org/download/windows/

2. Restore the database:
   psql -U postgres -c "CREATE USER epstein_user WITH PASSWORD 'epstein_local_pw_2024';"
   psql -U postgres -c "CREATE DATABASE epstein_documents OWNER epstein_user;"
   pg_restore -U postgres -d epstein_documents "$BackupsPath\epstein_backup.dump"

3. Update database paths (Linux to Windows):
   Run: .\scripts\update-database-paths.ps1

4. Configure and start the application:
   Run: .\scripts\migrate-to-bobbyhomeep.ps1 -SkipFiles -SkipDatabase

"@ -ForegroundColor Yellow
