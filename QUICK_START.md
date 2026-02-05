# Quick Start Guide - Dataset 9 Downloader

## Fastest Way to Start

### 1. Double-Click to Run

```
C:\Development\JaxSun.Ideas\tools\EpsteinDownloader\BUILD_AND_RUN.bat
```

That's it! The application will:
- ✅ Check for .NET SDK
- ✅ Restore packages
- ✅ Build the application
- ✅ Launch the GUI

### 2. Click "Start Download"

The GUI will appear with:
- Progress bar showing overall progress
- Text box showing detailed log
- Start/Stop buttons

Click **"Start Download"** and the application will:
1. Download 1.2M+ file URLs from Archive.org (~2 minutes)
2. Show embedded browser for age verification
3. **Automatically click both verification buttons**
4. Start downloading PDFs with progress updates

## What to Expect

### First Time Running

```
[10:30:15] WebView2 initialized successfully
[10:30:16] Ready to download
[Click "Start Download"]
[10:30:20] Step 1: Loading URL list from Archive.org
[10:30:21] Downloading URL list from Archive.org...
[10:30:22] Downloading 78.2 MB...
[10:32:15] URL list downloaded
[10:32:16] Parsing URLs...
[10:32:45] Found 1,223,757 PDF files to download
[10:32:46] Already downloaded: 0 files
[10:32:46] Remaining to download: 1,223,757 files
[10:32:47] Step 2: Age verification
[10:32:48] Navigating to age verification page...
[10:32:51] Looking for 'I am not a robot' button...
[10:32:52] ✓ Robot button clicked!
[10:32:55] Looking for age verification button...
[10:32:56] ✓ Age verification button clicked!
[10:32:59] Age verification complete - cookies set
[10:33:00] Step 3: Downloading 1,223,757 files
[10:33:01] [1/1223757] [OK] EFTA00039025.pdf (11,618,125 bytes)
[10:33:02] [2/1223757] [404] EFTA00039026.pdf
[10:33:03] [3/1223757] [OK] EFTA00039027.pdf (2,340,891 bytes)
...
```

### Resume After Stopping

```
[14:25:10] Loaded progress: Last index 45231
[14:25:11] Already downloaded: 32,145 files
[14:25:12] Remaining to download: 1,191,612 files
[14:25:13] Age verification already complete
[14:25:14] Step 3: Downloading 1,191,612 files
[14:25:15] [45232/1223757] [OK] EFTA00085256.pdf (5,123,456 bytes)
...
```

## Requirements Check

### ✅ .NET 9.0 SDK

**Check if installed:**
```cmd
dotnet --version
```

**Should show:** `9.0.x` or higher

**If not installed:**
Download from https://dotnet.microsoft.com/download/dotnet/9.0

### ✅ WebView2 Runtime

**Usually pre-installed on Windows 11**

**If you get "WebView2 not found" error:**
Download from https://developer.microsoft.com/microsoft-edge/webview2/

### ✅ Disk Space

**Minimum:** 500 GB free

**Check:**
```cmd
dir C:\
```

Look for "bytes free" at the bottom.

## Output Location

Downloaded files go to:
```
C:\Development\JaxSun.Ideas\tools\EpsteinDownloader\epstein_files\DataSet_9\
```

You can change this by editing `MainForm.cs` line 18:
```csharp
private readonly string outputDir = "D:\\EpsteinFiles\\DataSet_9"; // Your custom path
```

## Stop and Resume

### To Stop
- Click **"Stop"** button
- Or close the application
- Or press Alt+F4

### To Resume
- Run the application again
- Click **"Start Download"**
- It will automatically:
  - Skip already-downloaded files
  - Resume from where it stopped
  - Continue with remaining files

## Monitoring Progress

### In the Application
- **Progress Bar:** Shows percentage complete
- **Status Label:** Shows current operation and counts
- **Log TextBox:** Shows detailed file-by-file progress

### Expected Stats
- **Rate:** ~3 files/second (rate limited)
- **ETA:** Updates every 100 files
- **Success Rate:** Varies (many files are 404)

### Example Progress Update
```
[PROGRESS] Rate: 2.8 files/sec | ETA: 121:45:32
Downloaded: 32,145 | Errors: 13,086 | Progress: 45,231/1,223,757
```

## Troubleshooting

### Issue: "NET SDK not found"
**Solution:** Install .NET 9.0 SDK from https://dotnet.microsoft.com/download

### Issue: "WebView2 Runtime not found"
**Solution:** Install from https://developer.microsoft.com/microsoft-edge/webview2/

### Issue: Age verification buttons don't auto-click
**Solution:** The browser window will stay visible - click them manually and download will continue

### Issue: All files show "Not a PDF" error
**Solution:** Age verification failed. Restart the application - it will re-verify automatically.

### Issue: Very slow download
**Solution:** This is normal! Rate limiting ensures we don't overload DOJ servers. 3 files/sec = 4-5 days for 1.2M files.

### Issue: Application crashes
**Solution:** Just run it again! Progress is saved every 100 files, so you'll resume from near where it crashed.

## Advanced Usage

### Build Only (Don't Run)
```cmd
dotnet build -c Release
```

### Run Pre-Built Executable
```cmd
bin\Release\net9.0-windows\EpsteinDownloader.exe
```

### Run in Debug Mode
```cmd
dotnet run
```

## Performance Tips

### Maximize Download Speed
- Close other applications using internet
- Connect via Ethernet (not WiFi)
- Disable Windows Update during download
- Don't let computer sleep

### Minimize Interruptions
- Set Windows power plan to "Never sleep"
- Disable screen saver
- Keep laptop plugged in
- Monitor disk space periodically

## Expected Timeline

| Milestone | Time | Files |
|-----------|------|-------|
| URL list download | 2-3 min | 1 file (79 MB) |
| URL parsing | 30 sec | Processing 1.2M URLs |
| Age verification | 10 sec | Automatic |
| First 10,000 files | ~1 hour | At 3 files/sec |
| First 100,000 files | ~9 hours | " |
| Half complete | ~2.5 days | 612k files |
| Full download | ~4-5 days | 1.2M files |

## Files Created

```
epstein_files/DataSet_9/
├── archive_org_url_list.txt       # 79 MB - URL list from Archive.org
├── download_progress.json         # Progress tracking for resume
├── EFTA00039025.pdf              # Downloaded PDFs
├── EFTA00039027.pdf
├── EFTA00039028.pdf
└── ... (1.2 million more PDFs)
```

---

**Ready? Just double-click `BUILD_AND_RUN.bat` and click "Start Download"!** 🚀
