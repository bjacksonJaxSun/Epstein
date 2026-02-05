# Find which files we still need to download

$actualFiles = Get-Content "epstein_files\DataSet_9\actual_filenames.txt"
$downloadedFiles = Get-ChildItem "epstein_files\DataSet_9\*.pdf" | Select-Object -ExpandProperty Name

$remaining = @()

foreach ($file in $actualFiles) {
    if ($downloadedFiles -notcontains $file) {
        $remaining += $file
    }
}

Write-Host "Already Downloaded: $($downloadedFiles.Count)" -ForegroundColor Green
Write-Host "Total in Dataset: $($actualFiles.Count)" -ForegroundColor Cyan
Write-Host "Still Need: $($remaining.Count)" -ForegroundColor Yellow

# Save remaining files
$remaining | Out-File "epstein_files\DataSet_9\remaining_to_download.txt" -Encoding UTF8

# Create remaining URLs
$baseUrl = "https://www.justice.gov/epstein/files/DataSet%209/"
$remainingUrls = $remaining | ForEach-Object { $baseUrl + $_.Replace(' ', '%20') }
$remainingUrls | Out-File "epstein_files\DataSet_9\remaining_urls.txt" -Encoding UTF8

Write-Host "`nSaved to:"
Write-Host "  remaining_to_download.txt ($($remaining.Count) files)"
Write-Host "  remaining_urls.txt"

Write-Host "`nFirst 10 remaining:"
$remaining | Select-Object -First 10 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
