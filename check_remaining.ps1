$actualFiles = Get-Content "epstein_files\DataSet_9\actual_filenames.txt"
$downloadedFiles = Get-ChildItem "epstein_files\DataSet_9\*.pdf" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name

$downloadedSet = @{}
foreach ($f in $downloadedFiles) { $downloadedSet[$f] = $true }

$have = 0
$need = 0
foreach ($f in $actualFiles) {
    if ($downloadedSet.ContainsKey($f)) { $have++ } else { $need++ }
}

Write-Host "Total in dataset:    $($actualFiles.Count)"
Write-Host "Already downloaded:  $have"
Write-Host "Still need:          $need"
Write-Host "Progress:            $([math]::Round($have / $actualFiles.Count * 100, 1))%"
