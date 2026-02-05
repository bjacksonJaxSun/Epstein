Write-Host "================================================================================
Error Type Analysis
================================================================================
" -ForegroundColor Cyan

# Sample recent files to understand the pattern
$baseUrl = "https://www.justice.gov/epstein/files/DataSet%209/"
$testFiles = @(
    "EFTA00075000.pdf",
    "EFTA00075001.pdf",
    "EFTA00075002.pdf",
    "EFTA00075003.pdf",
    "EFTA00075004.pdf",
    "EFTA00075005.pdf",
    "EFTA00075006.pdf",
    "EFTA00075007.pdf",
    "EFTA00075008.pdf",
    "EFTA00075009.pdf"
)

Write-Host "Testing 10 consecutive files to understand error pattern..." -ForegroundColor Yellow
Write-Host ""

$found = 0
$notFound = 0
$otherErrors = 0

foreach ($file in $testFiles) {
    $url = $baseUrl + $file
    try {
        $response = Invoke-WebRequest -Uri $url -Method Head -TimeoutSec 5 -ErrorAction Stop
        Write-Host "[FOUND] $file - $($response.StatusCode)" -ForegroundColor Green
        $found++
    }
    catch {
        if ($_.Exception.Response.StatusCode.value__ -eq 404) {
            Write-Host "[404] $file - File does not exist on server" -ForegroundColor Gray
            $notFound++
        }
        else {
            Write-Host "[ERROR] $file - $($_.Exception.Message)" -ForegroundColor Red
            $otherErrors++
        }
    }
}

Write-Host ""
Write-Host "Results:" -ForegroundColor Yellow
Write-Host "  Found: $found" -ForegroundColor Green
Write-Host "  404 Not Found: $notFound" -ForegroundColor Gray
Write-Host "  Other Errors: $otherErrors" -ForegroundColor Red
Write-Host ""

$expectedErrorRate = ($notFound / $testFiles.Count) * 100
Write-Host "Expected Error Rate: $([math]::Round($expectedErrorRate))%" -ForegroundColor Cyan

if ($notFound -gt 7) {
    Write-Host ""
    Write-Host "ANALYSIS: This is NORMAL for Dataset 9" -ForegroundColor Green
    Write-Host "  - The dataset has sparse file coverage"
    Write-Host "  - Most file numbers don't have actual PDFs"
    Write-Host "  - 404 errors are expected and don't indicate a problem"
    Write-Host "  - The downloader will find ~5-10% actual files"
}

if ($otherErrors -gt 0) {
    Write-Host ""
    Write-Host "WARNING: Non-404 errors detected!" -ForegroundColor Red
    Write-Host "  - This may indicate session expiration or network issues" -ForegroundColor Red
    Write-Host "  - Monitor for patterns of consecutive failures" -ForegroundColor Red
}

Write-Host ""
Write-Host "Checking actual download directory..." -ForegroundColor Yellow
$pdfCount = (Get-ChildItem "epstein_files\DataSet_9\*.pdf" -ErrorAction SilentlyContinue).Count
Write-Host "  Total PDFs Downloaded: $pdfCount" -ForegroundColor Cyan

$recentPdfs = Get-ChildItem "epstein_files\DataSet_9\*.pdf" -ErrorAction SilentlyContinue |
              Sort-Object LastWriteTime -Descending |
              Select-Object -First 10

if ($recentPdfs) {
    Write-Host ""
    Write-Host "Last 10 successful downloads:" -ForegroundColor Yellow
    foreach ($pdf in $recentPdfs) {
        $timeAgo = (Get-Date) - $pdf.LastWriteTime
        $size = [math]::Round($pdf.Length / 1KB)
        Write-Host "  $($pdf.Name) - $size KB - $([math]::Round($timeAgo.TotalSeconds))s ago" -ForegroundColor Gray
    }
}
