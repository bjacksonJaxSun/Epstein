# Dataset 9 Epstein Files Downloader - C# Windows Application

A native Windows application to download Dataset 9 files from the DOJ Epstein library with automatic age verification.

## Features

✅ **Automatic Age Verification** - Clicks both "I am not a robot" and age verification buttons automatically
✅ **Resume Capability** - Automatically skips already-downloaded files
✅ **Progress Tracking** - Real-time progress display with file counts and ETA
✅ **Error Handling** - Robust error handling with detailed logging
✅ **Rate Limiting** - Respects server resources with 0.3s delay between downloads
✅ **Progress Persistence** - Saves progress every 100 files for safe resume

## Requirements

- **Windows 10/11**
- **.NET 9.0 SDK** - Download from https://dotnet.microsoft.com/download
- **WebView2 Runtime** - Usually pre-installed on Windows 11, download from https://developer.microsoft.com/microsoft-edge/webview2/

## Installation

### Option 1: Build from Source

```cmd
cd C:\Development\JaxSun.Ideas\tools\EpsteinDownloader
dotnet restore
dotnet build -c Release
```

### Option 2: Run Directly

```cmd
cd C:\Development\JaxSun.Ideas\tools\EpsteinDownloader
dotnet run
```

## Usage

1. **Launch the application**
   ```cmd
   dotnet run
   ```
   Or run the built executable:
   ```cmd
   bin\Release\net9.0-windows\EpsteinDownloader.exe
   ```

2. **Click "Start Download"**
   - Application will download the URL list from Archive.org (if needed)
   - Browser window will briefly appear for age verification
   - Buttons will be clicked automatically
   - Download will begin

3. **Monitor Progress**
   - Progress bar shows overall completion percentage
   - Text box shows detailed log of all operations
   - Status label shows current operation and file counts

4. **Stop/Resume**
   - Click "Stop" to pause download
   - Run again and click "Start Download" to resume
   - Already-downloaded files are automatically skipped

## Output Location

All files are downloaded to:
```
C:\Development\JaxSun.Ideas\tools\EpsteinDownloader\epstein_files\DataSet_9\
```

Files created:
- `*.pdf` - Downloaded PDF files
- `archive_org_url_list.txt` - URL list from Archive.org (79 MB)
- `download_progress.json` - Progress tracking for resume capability

## How It Works

### Step 1: Load URL List
- Downloads 1.2M+ file URLs from Archive.org (if not already present)
- Parses all PDF URLs
- Checks which files are already downloaded
- Calculates remaining files

### Step 2: Age Verification
- Opens embedded browser to https://www.justice.gov/age-verify
- Waits for page to load
- Automatically clicks "I am not a robot" button
- Automatically clicks "Yes" (18+) button
- Extracts cookies for authenticated downloads
- Hides browser once complete

### Step 3: Download Files
- Uses authenticated session with cookies from step 2
- Downloads each PDF file
- Validates file is actually a PDF (checks magic bytes: %PDF)
- Skips already-downloaded files
- Logs progress every file
- Saves progress every 100 files
- Rate limits to 0.3 seconds between files

## Progress Tracking

The application saves progress to `download_progress.json`:
```json
{
  "LastProcessedIndex": 45231,
  "SuccessCount": 32145,
  "ErrorCount": 13086,
  "LastUpdate": "2026-02-02T10:30:00"
}
```

This allows safe resumption after:
- Stopping the application
- Network interruptions
- Computer restarts
- Application crashes

## Performance

- **Speed:** ~3 files/second (rate limited)
- **Total files:** 1,224,009 PDFs
- **Estimated time:** 4-5 days continuous
- **Estimated size:** 100-500 GB
- **Success rate:** Varies (many files return 404)

## Troubleshooting

### "WebView2 Runtime not found"

Install from: https://developer.microsoft.com/microsoft-edge/webview2/

### Age verification fails

The application will keep the browser window visible if auto-click fails. Manually click the buttons and the download will continue.

### Download gets "Not a PDF" errors

This means age verification cookies expired or weren't set correctly. Restart the application - age verification will run again.

### Slow download speed

This is intentional rate limiting (0.3s between files) to respect DOJ servers. Do not modify this.

## Code Structure

```
EpsteinDownloader/
├── EpsteinDownloader.csproj    # Project file with dependencies
├── Program.cs                  # Application entry point
├── MainForm.cs                 # Main UI and download logic
└── README.md                   # This file
```

## Dependencies

- **Microsoft.Web.WebView2** - Browser control for age verification
- **Newtonsoft.Json** - JSON parsing for URL list and progress tracking

## Technical Details

### Age Verification Implementation

```csharp
// Navigate to verification page
webView.CoreWebView2.Navigate("https://www.justice.gov/age-verify");

// Click buttons via JavaScript
var script = @"
    (function() {
        var button = document.querySelector('input[value=""I am not a robot""]');
        if (button && button.offsetParent !== null) {
            button.click();
            return true;
        }
        return false;
    })();
";
await webView.CoreWebView2.ExecuteScriptAsync(script);

// Extract cookies for authenticated requests
var cookies = await webView.CoreWebView2.CookieManager.GetCookiesAsync("https://www.justice.gov");
```

### Resume Logic

```csharp
// Check if file exists and is valid
if (File.Exists(filePath) && IsValidPdf(filePath))
{
    // Skip already downloaded
    continue;
}

// Validate PDF magic bytes
bool IsValidPdf(string path)
{
    var buffer = new byte[4];
    File.OpenRead(path).Read(buffer, 0, 4);
    return buffer[0] == 0x25 && buffer[1] == 0x50
        && buffer[2] == 0x44 && buffer[3] == 0x46; // %PDF
}
```

## License

This tool downloads publicly available government documents released under the Epstein Files Transparency Act.

## Ethical Use

This tool is intended for:
- ✅ Research
- ✅ Journalism
- ✅ Transparency and accountability
- ✅ Archival purposes

Not for:
- ❌ Harassment
- ❌ Illegal purposes
- ❌ Overwhelming DOJ servers (hence the rate limiting)

## Support

For issues or questions:
1. Check this README
2. Verify WebView2 Runtime is installed
3. Ensure .NET 9.0 SDK is installed
4. Check application logs in the text box

---

**Ready to download 1.2 million files with automatic age verification!** 🚀
