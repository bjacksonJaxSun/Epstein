$progressFile = "epstein_files\DataSet_9\download_progress.json"
$destFolder = "epstein_files\DataSet_9"

Write-Host "================================================================================
Error Monitor - Dataset 9 Downloader
================================================================================
" -ForegroundColor Cyan

$lastIndex = 0
$lastSuccess = 0
$lastError = 0
$errorRate = 0
$consecutiveErrors = 0

while ($true) {
    Clear-Host
    Write-Host "================================================================================
Error Monitor - Dataset 9 Downloader
================================================================================
" -ForegroundColor Cyan

    if (Test-Path $progressFile) {
        $progress = Get-Content $progressFile | ConvertFrom-Json
        $currentIndex = $progress.LastProcessedIndex
        $currentSuccess = $progress.SuccessCount
        $currentError = $progress.ErrorCount

        # Calculate rates
        $processed = $currentIndex - $lastIndex
        $successDelta = $currentSuccess - $lastSuccess
        $errorDelta = $currentError - $lastError

        if ($processed -gt 0) {
            $errorRate = [math]::Round(($errorDelta / $processed) * 100, 1)
            $consecutiveErrors = if ($successDelta -eq 0 -and $errorDelta -gt 0) { $errorDelta } else { 0 }
        }

        Write-Host "Current Progress:" -ForegroundColor Yellow
        Write-Host "  Index: $currentIndex / 1,223,757"
        Write-Host "  Success: $currentSuccess"
        Write-Host "  Errors: $currentError"
        Write-Host "  Last Update: $($progress.LastUpdate)"
        Write-Host ""

        Write-Host "Recent Activity (last 10 seconds):" -ForegroundColor Yellow
        Write-Host "  Files Processed: $processed"
        Write-Host "  Successful: $successDelta" -ForegroundColor Green
        Write-Host "  Errors: $errorDelta" -ForegroundColor Red
        Write-Host "  Error Rate: $errorRate%" -ForegroundColor $(if ($errorRate -gt 90) { "Red" } elseif ($errorRate -gt 50) { "Yellow" } else { "Green" })
        Write-Host ""

        if ($consecutiveErrors -gt 0) {
            Write-Host "WARNING: $consecutiveErrors consecutive errors!" -ForegroundColor Red
            Write-Host "  This may indicate session expiration or network issues." -ForegroundColor Red
        }

        Write-Host ""
        Write-Host "Error Analysis:" -ForegroundColor Yellow
        $totalProcessed = $currentIndex
        $overallErrorRate = [math]::Round(($currentError / $totalProcessed) * 100, 1)
        Write-Host "  Overall Error Rate: $overallErrorRate%"

        if ($overallErrorRate -gt 95) {
            Write-Host "  Status: CRITICAL - Most files are 404 errors (expected for this dataset)" -ForegroundColor Yellow
        } elseif ($overallErrorRate -gt 80) {
            Write-Host "  Status: HIGH - Many files don't exist on server" -ForegroundColor Yellow
        } elseif ($errorRate -gt 50) {
            Write-Host "  Status: NORMAL - Mix of successes and 404s" -ForegroundColor Green
        } else {
            Write-Host "  Status: EXCELLENT - Most files downloading successfully" -ForegroundColor Green
        }

        Write-Host ""
        Write-Host "Recent Files:" -ForegroundColor Yellow
        $recentPdfs = Get-ChildItem "$destFolder\*.pdf" -ErrorAction SilentlyContinue |
                      Sort-Object LastWriteTime -Descending |
                      Select-Object -First 5

        if ($recentPdfs) {
            foreach ($pdf in $recentPdfs) {
                $timeAgo = (Get-Date) - $pdf.LastWriteTime
                $size = [math]::Round($pdf.Length / 1MB, 2)
                Write-Host "  $($pdf.Name) - $size MB - $([math]::Round($timeAgo.TotalSeconds))s ago" -ForegroundColor Gray
            }
        } else {
            Write-Host "  No recent downloads" -ForegroundColor Gray
        }

        # Check for zip files
        $zipFolder = "$destFolder\zipped"
        if (Test-Path $zipFolder) {
            $zipCount = (Get-ChildItem "$zipFolder\*.zip" -ErrorAction SilentlyContinue).Count
            Write-Host ""
            Write-Host "Zip Batches Created: $zipCount" -ForegroundColor Cyan
        }

        $lastIndex = $currentIndex
        $lastSuccess = $currentSuccess
        $lastError = $currentError
    } else {
        Write-Host "Progress file not found. Waiting for download to start..." -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "Refreshing in 10 seconds... (Ctrl+C to stop)" -ForegroundColor Gray
    Start-Sleep -Seconds 10
}
