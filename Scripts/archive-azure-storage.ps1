# archive-azure-storage.ps1
# Applies an Azure Lifecycle Management Policy to move all block blobs in
# epsteinstorage2024 to Cold tier (immediately accessible, ~75% cheaper than Hot).
#
# Cold tier: $0.0045/GB/month vs Hot $0.018/GB/month
# 103 GB estimated savings: ~$1.85 -> ~$0.46/month
# Note: 90-day minimum retention — early deletion incurs prorated fee.
#
# Usage: .\Scripts\archive-azure-storage.ps1
# Prerequisites: az CLI installed, az login completed

$StorageAccount = "epsteinstorage2024"

# Ensure az CLI and system paths are available
$env:PATH = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')

$azCliPath = "C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin"
if ((Test-Path $azCliPath) -and ($env:PATH -notlike "*$azCliPath*")) {
    $env:PATH = "$azCliPath;$env:PATH"
}

# Verify az is accessible
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Error "az CLI not found. Install from https://aka.ms/installazurecliwindows and run az login."
    exit 1
}

Write-Host "Looking up resource group for storage account '$StorageAccount'..." -ForegroundColor Cyan

$resourceGroup = az storage account list `
    --query "[?name=='$StorageAccount'].resourceGroup | [0]" `
    --output tsv 2>&1

if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($resourceGroup)) {
    Write-Error "Could not find storage account '$StorageAccount'. Make sure you are logged in (az login) and have access."
    exit 1
}

Write-Host "Found resource group: $resourceGroup" -ForegroundColor Green

# Build lifecycle policy JSON
$policy = @{
    rules = @(
        @{
            name    = "move-all-to-cold"
            enabled = $true
            type    = "Lifecycle"
            definition = @{
                actions = @{
                    baseBlob = @{
                        tierToCold = @{
                            daysAfterModificationGreaterThan = 0
                        }
                    }
                }
                filters = @{
                    blobTypes = @("blockBlob")
                }
            }
        }
    )
}

$policyFile = [System.IO.Path]::GetTempFileName() + ".json"
$policy | ConvertTo-Json -Depth 10 | Set-Content -Path $policyFile -Encoding UTF8

Write-Host "Policy JSON written to: $policyFile" -ForegroundColor Gray
Write-Host ""
Write-Host "Applying lifecycle management policy..." -ForegroundColor Cyan

az storage account management-policy create `
    --account-name $StorageAccount `
    --resource-group $resourceGroup `
    --policy "@$policyFile"

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to apply lifecycle policy."
    Remove-Item $policyFile -ErrorAction SilentlyContinue
    exit 1
}

Remove-Item $policyFile -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Policy applied successfully. Current policy:" -ForegroundColor Green

az storage account management-policy show `
    --account-name $StorageAccount `
    --resource-group $resourceGroup

Write-Host ""
Write-Host "========================================" -ForegroundColor Yellow
Write-Host "NEXT STEPS" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host "Azure will process this policy within 24-48 hours."
Write-Host "All block blobs in '$StorageAccount' will be moved to Cold tier."
Write-Host ""
Write-Host "To verify after 24-48 hours, spot-check a blob tier:"
Write-Host "  az storage blob show \"
Write-Host "      --account-name $StorageAccount \"
Write-Host "      --container-name epstein-files \"
Write-Host "      --name `"VOL00010/VOL00010/DataSet_6/<filename>`" \"
Write-Host "      --query `"properties.blobTier`""
Write-Host ""
Write-Host "Expected result: `"Cold`""
Write-Host ""
Write-Host "Cold tier files are immediately accessible (no rehydration)."
Write-Host "Re-run Scripts\download-files.ps1 to download any files in future."
