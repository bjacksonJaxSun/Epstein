# Upload Missing PDFs to Azure VM
# Run this script from PowerShell on your Windows machine

$ErrorActionPreference = "Continue"
$AzureVM = "azureuser@20.25.96.123"
$SshKey = "$env:USERPROFILE\.ssh\azure_vm"
$RemoteBase = "/data/epstein_files/missing_pdfs"

# Progress tracking
$script:totalFilesAllDatasets = 0
$script:uploadedFilesAllDatasets = 0
$script:startTime = Get-Date

function Show-Progress {
    param($Current, $Total, $Dataset, $Phase)

    $percent = if ($Total -gt 0) { [math]::Round(($Current / $Total) * 100, 1) } else { 0 }
    $elapsed = (Get-Date) - $script:startTime
    $elapsedStr = "{0:hh\:mm\:ss}" -f $elapsed

    # Calculate ETA
    if ($Current -gt 0 -and $script:uploadedFilesAllDatasets -gt 0) {
        $rate = $script:uploadedFilesAllDatasets / $elapsed.TotalSeconds
        $remaining = ($script:totalFilesAllDatasets - $script:uploadedFilesAllDatasets) / $rate
        $eta = [TimeSpan]::FromSeconds($remaining)
        $etaStr = "{0:hh\:mm\:ss}" -f $eta
    } else {
        $etaStr = "--:--:--"
    }

    $bar = "[" + ("=" * [math]::Floor($percent / 5)) + (" " * (20 - [math]::Floor($percent / 5))) + "]"

    Write-Host "`r$Dataset $Phase $bar $percent% ($Current/$Total) | Elapsed: $elapsedStr | ETA: $etaStr    " -NoNewline
}

# Create remote directories
Write-Host "Creating remote directories..." -ForegroundColor Cyan
ssh -i $SshKey $AzureVM "mkdir -p $RemoteBase/dataset9 $RemoteBase/dataset8 $RemoteBase/dataset1 $RemoteBase/dataset2"

# Dataset configurations
$datasets = @(
    @{
        Name = "Dataset9"
        ListFile = "\\bobbyhomeep\EpsteinDownloader\epstein_extraction\needed_dataset9.txt"
        SourcePath = "\\Bobbyhomeep\d\dataset9-pdfs"
        RemotePath = "$RemoteBase/dataset9"
    },
    @{
        Name = "Dataset8"
        ListFile = "\\bobbyhomeep\EpsteinDownloader\epstein_extraction\needed_dataset8.txt"
        SourcePath = "\\Bobbyhomeep\d\DataSet8_extracted"
        RemotePath = "$RemoteBase/dataset8"
    },
    @{
        Name = "Dataset1"
        ListFile = "\\bobbyhomeep\EpsteinDownloader\epstein_extraction\needed_dataset1.txt"
        SourcePath = "\\Bobbyhomeep\d\DataSet1_extracted"
        RemotePath = "$RemoteBase/dataset1"
    },
    @{
        Name = "Dataset2"
        ListFile = "\\bobbyhomeep\EpsteinDownloader\epstein_extraction\needed_dataset2.txt"
        SourcePath = "\\Bobbyhomeep\d\DataSet2_extracted"
        RemotePath = "$RemoteBase/dataset2"
    }
)

function Upload-Dataset {
    param($Dataset)

    Write-Host "`n"
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host "Processing $($Dataset.Name)" -ForegroundColor Yellow
    Write-Host "Source: $($Dataset.SourcePath)" -ForegroundColor Gray
    Write-Host "========================================" -ForegroundColor Yellow

    if (-not (Test-Path $Dataset.ListFile)) {
        Write-Host "ERROR: List file not found: $($Dataset.ListFile)" -ForegroundColor Red
        return 0
    }

    if (-not (Test-Path $Dataset.SourcePath)) {
        Write-Host "ERROR: Source path not found: $($Dataset.SourcePath)" -ForegroundColor Red
        return 0
    }

    # Read needed EFTA numbers
    $neededFiles = Get-Content $Dataset.ListFile | Where-Object { $_ -match "EFTA\d+" }
    $neededSet = @{}
    foreach ($efta in $neededFiles) {
        $neededSet[$efta.Trim()] = $true
    }
    Write-Host "Loaded $($neededSet.Count) EFTA numbers from list" -ForegroundColor Cyan

    # Scan and match files
    Write-Host "Scanning source directory..." -ForegroundColor Cyan
    $filesToUpload = @()
    $scanned = 0

    Get-ChildItem -Path $Dataset.SourcePath -Filter "*.pdf" -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
        $scanned++
        if ($scanned % 500 -eq 0) {
            Write-Host "`rScanning... $scanned files checked, $($filesToUpload.Count) matched" -NoNewline
        }
        $efta = $_.BaseName
        if ($neededSet.ContainsKey($efta)) {
            $filesToUpload += $_
        }
    }
    Write-Host "`rScanned $scanned files, found $($filesToUpload.Count) to upload                    "

    if ($filesToUpload.Count -eq 0) {
        Write-Host "No files to upload for this dataset" -ForegroundColor Yellow
        return 0
    }

    # Upload files in batches
    $batchSize = 100
    $uploaded = 0
    $totalToUpload = $filesToUpload.Count

    Write-Host "Uploading $totalToUpload files in batches of $batchSize..." -ForegroundColor Cyan

    for ($i = 0; $i -lt $filesToUpload.Count; $i += $batchSize) {
        $batch = $filesToUpload[$i..([Math]::Min($i + $batchSize - 1, $filesToUpload.Count - 1))]

        # Create temp batch directory
        $tempDir = Join-Path $env:TEMP "upload_batch_$($Dataset.Name)"
        if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
        New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

        # Copy batch to temp
        foreach ($file in $batch) {
            Copy-Item $file.FullName $tempDir -ErrorAction SilentlyContinue
        }

        # Upload batch
        $scpOutput = scp -i $SshKey -r "$tempDir/*" "${AzureVM}:$($Dataset.RemotePath)/" 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "`nSCP Error: $scpOutput" -ForegroundColor Red
        }

        $uploaded += $batch.Count
        $script:uploadedFilesAllDatasets += $batch.Count

        Show-Progress -Current $uploaded -Total $totalToUpload -Dataset $Dataset.Name -Phase "Uploading"

        # Cleanup
        Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }

    Write-Host "`n$($Dataset.Name): Uploaded $uploaded files" -ForegroundColor Green
    return $uploaded
}

# First pass: count total files to upload
Write-Host "`nPhase 1: Calculating total files to upload..." -ForegroundColor Cyan
foreach ($dataset in $datasets) {
    if ((Test-Path $dataset.ListFile) -and (Test-Path $dataset.SourcePath)) {
        $neededFiles = Get-Content $dataset.ListFile | Where-Object { $_ -match "EFTA\d+" }
        $script:totalFilesAllDatasets += $neededFiles.Count
        Write-Host "  $($dataset.Name): ~$($neededFiles.Count) files" -ForegroundColor Gray
    }
}
Write-Host "Total files to process: ~$($script:totalFilesAllDatasets)" -ForegroundColor Cyan

# Process each dataset
Write-Host "`nPhase 2: Uploading files..." -ForegroundColor Cyan
$script:startTime = Get-Date
$totalUploaded = 0

foreach ($dataset in $datasets) {
    $uploaded = Upload-Dataset $dataset
    $totalUploaded += $uploaded
}

$elapsed = (Get-Date) - $script:startTime
$elapsedStr = "{0:hh\:mm\:ss}" -f $elapsed

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "UPLOAD COMPLETE!" -ForegroundColor Green
Write-Host "Total files uploaded: $totalUploaded" -ForegroundColor Green
Write-Host "Total time: $elapsedStr" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

# Update PDF index on remote
Write-Host "`nUpdating PDF index on Azure VM..." -ForegroundColor Cyan
ssh -i $SshKey $AzureVM "find /data/epstein_files/missing_pdfs -name '*.pdf' >> /tmp/pdf_index.txt && wc -l /tmp/pdf_index.txt"

Write-Host "`nDone! The uploaded PDFs are now indexed." -ForegroundColor Green
Write-Host "Run image extraction again to process the new files." -ForegroundColor Yellow
