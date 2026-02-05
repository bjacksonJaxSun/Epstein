@echo off
echo ================================================================================
echo Dataset 9 Downloader - Diagnostic Tool
echo ================================================================================
echo.

echo [CHECK 1] .NET SDK
dotnet --version
if errorlevel 1 (
    echo [FAIL] .NET SDK not found
    goto :end
) else (
    echo [OK] .NET SDK installed
)
echo.

echo [CHECK 2] WebView2 Runtime
reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" >nul 2>&1
if errorlevel 1 (
    echo [WARN] WebView2 may not be installed
    echo       Download from: https://developer.microsoft.com/microsoft-edge/webview2/
) else (
    echo [OK] WebView2 appears to be installed
)
echo.

echo [CHECK 3] Output Directory
if exist "epstein_files\DataSet_9" (
    echo [OK] Output directory exists
    cd epstein_files\DataSet_9
    echo       PDFs:
    dir /b *.pdf 2>nul | find /c /v "" || echo 0
    echo       URL list:
    if exist "archive_org_url_list.txt" (
        echo       [OK] Found
    ) else (
        echo       [MISSING] Not downloaded
    )
    cd ..\..
) else (
    echo [INFO] Output directory not created yet
)
echo.

echo [CHECK 4] Build Status
dotnet build -c Release >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Build failed - run: dotnet build
) else (
    echo [OK] Build successful
)
echo.

echo ================================================================================
echo Diagnostic Complete
echo ================================================================================
echo.
echo To run the application:
echo   dotnet run
echo.
:end
pause
