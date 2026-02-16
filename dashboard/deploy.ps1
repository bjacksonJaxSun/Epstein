# Epstein Dashboard Deployment Script
# This script builds, publishes, and deploys the dashboard to the remote VM

param(
    [string]$Environment = "Production",
    [switch]$RunMigration = $false,
    [switch]$RestartService = $false,
    [switch]$BuildFrontend = $true,
    [switch]$BuildBackend = $true
)

$ErrorActionPreference = "Stop"

# Configuration
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ScriptDir "backend"
$FrontendDir = Join-Path $ScriptDir "frontend"
$PublishDir = Join-Path $BackendDir "publish"
$MigrationsDir = Join-Path $BackendDir "migrations"

# Database configuration (from appsettings.json)
$DbHost = "localhost"
$DbName = "epstein_documents"
$DbUser = "epstein_user"
$DbPassword = "epstein_secure_pw_2024"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Epstein Dashboard Deployment Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Build Frontend
if ($BuildFrontend) {
    Write-Host "[1/5] Building Frontend..." -ForegroundColor Yellow
    Push-Location $FrontendDir
    try {
        npm install --silent 2>&1 | Out-Null
        npm run build
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend build failed"
        }
        Write-Host "  Frontend build successful" -ForegroundColor Green
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "[1/5] Skipping Frontend build" -ForegroundColor DarkGray
}

# Step 2: Build and Publish Backend
if ($BuildBackend) {
    Write-Host "[2/5] Building and Publishing Backend..." -ForegroundColor Yellow
    Push-Location $BackendDir
    try {
        # Clean previous publish
        if (Test-Path $PublishDir) {
            Remove-Item -Path $PublishDir -Recurse -Force
        }

        # Restore and publish
        dotnet restore --verbosity quiet
        dotnet publish src/EpsteinDashboard.Api -c Release -o $PublishDir --verbosity minimal

        if ($LASTEXITCODE -ne 0) {
            throw "Backend publish failed"
        }
        Write-Host "  Backend publish successful" -ForegroundColor Green
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Host "[2/5] Skipping Backend build" -ForegroundColor DarkGray
}

# Step 3: Run Database Migrations
if ($RunMigration) {
    Write-Host "[3/5] Running Database Migrations..." -ForegroundColor Yellow

    $MigrationFiles = Get-ChildItem -Path $MigrationsDir -Filter "*.sql" | Sort-Object Name

    foreach ($file in $MigrationFiles) {
        Write-Host "  Applying: $($file.Name)" -ForegroundColor Cyan

        $env:PGPASSWORD = $DbPassword
        $result = psql -h $DbHost -U $DbUser -d $DbName -f $file.FullName 2>&1

        if ($LASTEXITCODE -ne 0) {
            Write-Host "  Warning: Migration may have already been applied or encountered an error" -ForegroundColor Yellow
            Write-Host "  $result" -ForegroundColor DarkGray
        }
        else {
            Write-Host "  Applied successfully" -ForegroundColor Green
        }
    }
}
else {
    Write-Host "[3/5] Skipping Database Migrations (use -RunMigration to apply)" -ForegroundColor DarkGray
}

# Step 4: Copy Frontend dist to Backend wwwroot
Write-Host "[4/5] Copying Frontend to Backend wwwroot..." -ForegroundColor Yellow
$FrontendDist = Join-Path $FrontendDir "dist"
$BackendWwwroot = Join-Path $PublishDir "wwwroot"

if (Test-Path $FrontendDist) {
    if (-not (Test-Path $BackendWwwroot)) {
        New-Item -ItemType Directory -Path $BackendWwwroot -Force | Out-Null
    }
    Copy-Item -Path "$FrontendDist\*" -Destination $BackendWwwroot -Recurse -Force
    Write-Host "  Frontend assets copied to wwwroot" -ForegroundColor Green
}
else {
    Write-Host "  Warning: Frontend dist folder not found" -ForegroundColor Yellow
}

# Step 5: Restart Service (if requested)
if ($RestartService) {
    Write-Host "[5/5] Restarting Service..." -ForegroundColor Yellow

    # Try to restart as a Windows service
    $ServiceName = "EpsteinDashboard"
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue

    if ($service) {
        Restart-Service -Name $ServiceName
        Write-Host "  Service restarted" -ForegroundColor Green
    }
    else {
        Write-Host "  Service '$ServiceName' not found. Please restart manually:" -ForegroundColor Yellow
        Write-Host "    cd $PublishDir" -ForegroundColor DarkGray
        Write-Host "    dotnet EpsteinDashboard.Api.dll" -ForegroundColor DarkGray
    }
}
else {
    Write-Host "[5/5] Skipping Service Restart (use -RestartService to restart)" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Published to: $PublishDir" -ForegroundColor White
Write-Host ""
Write-Host "To start the application manually:" -ForegroundColor White
Write-Host "  cd $PublishDir" -ForegroundColor DarkGray
Write-Host "  dotnet EpsteinDashboard.Api.dll" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Default admin credentials:" -ForegroundColor White
Write-Host "  Username: admin" -ForegroundColor DarkGray
Write-Host "  Password: ChangeMe123! (or ADMIN_INITIAL_PASSWORD env var)" -ForegroundColor DarkGray
