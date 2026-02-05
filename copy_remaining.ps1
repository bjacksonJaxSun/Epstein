$source = "C:\Development\JaxSun.Ideas\scripts\epstein_files\DataSet_9"
$dest = "C:\Development\JaxSun.Ideas\tools\EpsteinDownloader\epstein_files\DataSet_9"

$sourceFiles = Get-ChildItem "$source\*.pdf"
$copied = 0

foreach ($file in $sourceFiles) {
    $destPath = Join-Path $dest $file.Name
    if (-not (Test-Path $destPath)) {
        Copy-Item $file.FullName $destPath
        $copied++
        if ($copied % 100 -eq 0) {
            Write-Host "Copied $copied files..."
        }
    }
}

Write-Host "Total files copied: $copied"
Write-Host "Verifying counts..."
$sourceCount = (Get-ChildItem "$source\*.pdf").Count
$destCount = (Get-ChildItem "$dest\*.pdf").Count
Write-Host "Source: $sourceCount files"
Write-Host "Destination: $destCount files"
