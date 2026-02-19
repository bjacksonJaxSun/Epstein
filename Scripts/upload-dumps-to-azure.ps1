$env:PATH = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User') + ';C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin'

$StorageAccount = "epsteinstorage2024"
$Container = "epstein-backups"
$DumpDir = "C:\Development\EpsteinDownloader\tmp"

Write-Host "=== Uploading database dumps to Azure Cold storage ==="

# Create backups container if it doesn't exist
Write-Host "Creating container '$Container'..."
az storage container create --account-name $StorageAccount --name $Container --auth-mode login 2>&1

# Get storage key for uploads
$key = az storage account keys list --account-name $StorageAccount --query '[0].value' --output tsv

$dumps = @(
    "epstein_db_fresh_20260219.dump",
    "backup_before_cleanup.sql",
    "epstein_db_full.dump"
)

foreach ($dump in $dumps) {
    $path = Join-Path $DumpDir $dump
    if (Test-Path $path) {
        $sizeMB = [math]::Round((Get-Item $path).Length / 1MB, 0)
        Write-Host "Uploading $dump ($sizeMB MB)..."
        az storage blob upload `
            --account-name $StorageAccount `
            --account-key $key `
            --container-name $Container `
            --name "db-backups/$dump" `
            --file $path `
            --tier Cold `
            --overwrite
        Write-Host "  Done."
    }
}

Write-Host ""
Write-Host "Listing uploaded blobs:"
az storage blob list --account-name $StorageAccount --account-key $key --container-name $Container --query '[].{name:name,size:properties.contentLength,tier:properties.blobTier}' --output table
