@echo off
REM Build and Run Epstein Downloader C# Application

echo ================================================================================
echo Dataset 9 Epstein Files Downloader - C# Windows Application
echo ================================================================================
echo.

REM Check if .NET 9 is installed
dotnet --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] .NET SDK not found
    echo.
    echo Please install .NET 9.0 SDK from:
    echo https://dotnet.microsoft.com/download/dotnet/9.0
    echo.
    pause
    exit /b 1
)

echo [INFO] .NET SDK found
dotnet --version
echo.

REM Restore dependencies
echo [STEP 1] Restoring NuGet packages...
dotnet restore
if errorlevel 1 (
    echo [ERROR] Failed to restore packages
    pause
    exit /b 1
)
echo [OK] Packages restored
echo.

REM Build application
echo [STEP 2] Building application...
dotnet build -c Release
if errorlevel 1 (
    echo [ERROR] Build failed
    pause
    exit /b 1
)
echo [OK] Build successful
echo.

REM Run application
echo [STEP 3] Launching application...
echo.
echo ================================================================================
echo Application starting...
echo ================================================================================
echo.

dotnet run -c Release

echo.
echo ================================================================================
echo Application closed
echo ================================================================================
pause
