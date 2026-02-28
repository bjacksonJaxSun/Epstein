# flatten-dataset-folders.ps1
# Removes the double-nesting artifact from SCP copies.
# Before: DataSet_N\DataSet_N\...files...
# After:  DataSet_N\...files...
#
# Usage:
#   .\flatten-dataset-folders.ps1              # Dry run (shows what would happen)
#   .\flatten-dataset-folders.ps1 -Execute     # Actually move files

param(
    [switch]$Execute,
    [string]$BasePath = "D:\Personal\Epstein\data\files"
)

if (-not (Test-Path $BasePath)) {
    Write-Error "Base path not found: $BasePath"
    exit 1
}

$folders = Get-ChildItem $BasePath -Directory
$totalMoved = 0

foreach ($outer in $folders) {
    $inner = Join-Path $outer.FullName $outer.Name
    if (-not (Test-Path $inner)) {
        Write-Host "  SKIP $($outer.Name) - no double-nesting found" -ForegroundColor Gray
        continue
    }

    Write-Host "  FOUND $($outer.Name)\$($outer.Name)\" -ForegroundColor Yellow

    if ($Execute) {
        Write-Host "    Moving contents up..." -ForegroundColor Cyan

        # Use robocopy to move all contents from inner to outer
        # /MOVE = move files (delete from source after copy)
        # /E    = include empty subdirectories
        # /NFL /NDL /NJH /NJS = suppress file/dir/header/summary logging (less noise)
        $robocopyArgs = @($inner, $outer.FullName, "/MOVE", "/E", "/NFL", "/NDL", "/NJH", "/NJS")
        & robocopy @robocopyArgs

        # robocopy exit codes: 0-7 are success, 8+ are errors
        if ($LASTEXITCODE -le 7) {
            # Remove the now-empty inner directory if it still exists
            if (Test-Path $inner) {
                Remove-Item $inner -Recurse -Force -ErrorAction SilentlyContinue
            }
            Write-Host "    OK - flattened $($outer.Name)" -ForegroundColor Green
            $totalMoved++
        } else {
            Write-Host "    ERROR - robocopy failed with exit code $LASTEXITCODE" -ForegroundColor Red
        }
    } else {
        Write-Host "    [DRY RUN] Would move contents from $($outer.Name)\$($outer.Name)\ to $($outer.Name)\" -ForegroundColor DarkYellow
        $totalMoved++
    }
}

Write-Host ""
if ($Execute) {
    Write-Host "Done. Flattened $totalMoved folders." -ForegroundColor Green
} else {
    Write-Host "Dry run complete. $totalMoved folders would be flattened." -ForegroundColor Cyan
    Write-Host "Run with -Execute to apply changes." -ForegroundColor Cyan
}
