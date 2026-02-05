# Dataset 9 Downloader - Enhanced Version with Auto-Recovery

## What's New - Version 2.0

### ✅ Automatic Session Recovery
The application now automatically handles session expiration and errors:

1. **Monitors Every Response**
   - Checks if downloads return PDFs or HTML
   - Detects age verification pages
   - Identifies authentication errors
   - Tracks consecutive error patterns

2. **Automatic Browser Restart**
   - When 10 consecutive errors occur → Restarts session
   - When age verification page detected → Restarts session
   - When 403/401 HTTP errors → Restarts session
   - Closes browser and re-does age verification automatically

3. **Smart Retry Logic**
   - Maximum 5 consecutive restart attempts
   - Resets failure counter on successful download
   - Maintains progress through all restarts
   - Never loses track of next file to download

4. **Browser Visibility**
   - Browser stays visible during entire download
   - Allows monitoring of verification process
   - Shows when session expires and restarts

5. **Enhanced Progress Tracking**
   - Shows consecutive failures count
   - Displays retry attempts (e.g., "Failures: 2/5")
   - Maintains position even during restarts
   - Progress saved every 100 files

## How It Works

### Normal Operation
```
[10:30:00] [1/1224009] [OK] EFTA00039025.pdf
[10:30:01] [2/1224009] [OK] EFTA00039026.pdf
[10:30:02] [3/1224009] [404] EFTA00039027.pdf
[10:30:03] [4/1224009] [OK] EFTA00039028.pdf
...
```

### Session Expiration Detected
```
[10:45:00] [1250/1224009] [ERROR] Not a PDF (got HTML)
[10:45:01] [1251/1224009] [ERROR] Not a PDF (got HTML)
[10:45:02] [1252/1224009] [ERROR] Not a PDF (got HTML)
...
[10:45:10] [1260/1224009] [ERROR] Not a PDF (got HTML)
[10:45:11] [SESSION ERROR] 10 consecutive errors - session likely expired
[10:45:12] [SESSION EXPIRED] Age verification required again
[10:45:13] [RETRY] Consecutive failures: 1/5
[10:45:14] [RESTART] Closing browser and restarting session...
[10:45:16] [BROWSER] Opening browser and navigating to site...
[10:45:17] [NAVIGATE] Going to age verification page...
[10:45:20] [STEP 1] Looking for 'I am not a robot' button...
[10:45:21] [SUCCESS] Robot button clicked!
[10:45:25] [STEP 2] Looking for 'Yes' (18+) button...
[10:45:26] [SUCCESS] Age verification button clicked!
[10:45:29] [INFO] Age verification completed - cookies set
[10:45:30] [INFO] Browser will remain visible for monitoring
[10:45:31] [1260/1224009] [OK] EFTA00040284.pdf
...continues downloading...
```

### Maximum Failures Reached
```
[12:30:00] [SESSION ERROR] 10 consecutive errors
[12:30:01] [RETRY] Consecutive failures: 5/5
[12:30:02] [FATAL] Maximum consecutive failures reached. Stopping.
[12:30:03] Failed after 5 retry attempts
```

## New Features Explained

### 1. Error Response Monitoring

The application now checks EVERY download response:

```csharp
// Check if it's actually a PDF
if (bytes[0] == 0x25 && bytes[1] == 0x50 ...) // %PDF
{
    // Success - continue downloading
}
else
{
    // Got HTML instead - check if it's age verification
    if (html.Contains("age-verify"))
    {
        // Trigger session restart
    }
}
```

### 2. Consecutive Error Tracking

- **Error streak** counts consecutive non-PDF responses
- **404 errors** don't count toward streak (expected)
- **Success** resets the error streak
- **10 consecutive errors** triggers session restart

### 3. Session Restart Process

When session restart is triggered:

1. Save current progress (which file to resume from)
2. Log the error and failure count
3. Close browser (releases resources)
4. Wait 2 seconds
5. Set `ageVerificationComplete = false`
6. Call `HandleAgeVerificationAsync()` again
7. Browser opens, navigates, clicks buttons
8. Resume downloading from saved position

### 4. Failure Limit Protection

Prevents infinite restart loops:

- Tracks `consecutiveFailures` counter
- Maximum allowed: **5 consecutive restart attempts**
- Counter resets when a batch completes successfully
- Stops permanently after 5 failures in a row

### 5. Progress Persistence

Progress is saved:
- Every 100 files
- Before each session restart
- Includes: last file index, success count, error count

```json
{
  "LastProcessedIndex": 45231,
  "SuccessCount": 32145,
  "ErrorCount": 13086,
  "LastUpdate": "2026-02-02T10:30:00"
}
```

## What This Means for You

### ✅ Benefits

1. **No Manual Intervention**
   - Application handles expired sessions automatically
   - Restarts verification without your help
   - Continues downloading where it left off

2. **Reliable Long-Running Downloads**
   - 4-5 day download can now complete unattended
   - Sessions that expire get refreshed automatically
   - No more waking up to find download stopped

3. **Better Error Handling**
   - Distinguishes between file-not-found and session errors
   - Only restarts when truly needed
   - Prevents infinite loops with failure limit

4. **Transparent Operation**
   - Browser stays visible so you can see what's happening
   - Detailed logs show every restart and retry
   - Progress updates include failure count

### ⚠️ Important Notes

1. **Browser Stays Visible**
   - Don't close the browser window manually
   - It needs to stay open for the entire download
   - It will restart itself when needed

2. **5 Restart Limit**
   - If 5 consecutive restarts fail, download stops
   - This prevents endless loops if something is broken
   - You can restart the application to try again

3. **Progress Always Saved**
   - Safe to stop application anytime (Click "Stop" or close window)
   - Progress saved every 100 files and before each restart
   - Resume will continue from last saved position

## Usage Examples

### Starting Fresh Download
```
1. Run: BUILD_AND_RUN.bat or dotnet run
2. Click "Start Download"
3. Watch browser window - buttons click automatically
4. Monitor progress in log text box
5. Let it run for days - restarts happen automatically
```

### Resuming After Stop
```
1. Run the application again
2. Click "Start Download"
3. Log shows: "Already downloaded: 32,145 files"
4. Continues from file 32,146
```

### Manual Intervention if Needed
```
If 5 consecutive failures occur:
1. Application stops and shows error
2. Check the browser window for issues
3. Close application
4. Wait a minute
5. Run again - starts fresh with 0 failures
```

## Technical Details

### Error Detection Thresholds

| Condition | Threshold | Action |
|-----------|-----------|--------|
| Consecutive errors | 10 | Restart session |
| Consecutive restarts | 5 | Stop permanently |
| Age verification detected | 1 | Restart immediately |
| 401/403 HTTP error | 1 | Restart immediately |

### Timing

| Operation | Duration |
|-----------|----------|
| Page load wait | 4 seconds |
| After robot button click | 4 seconds |
| After age button click | 3 seconds |
| Between restarts | 2 seconds |
| Between file downloads | 0.3 seconds |

### Browser Behavior

- **Visible during:** Entire download process
- **Shows:** Age verification page during restarts
- **Allows:** Visual monitoring of what's happening
- **Required:** Must stay open, don't close manually

## Upgrade from Version 1.0

If you were using the previous version:

1. **Stop the old version** if it's running
2. **Build the new version**: `dotnet build -c Release`
3. **Run the new version**: `dotnet run` or `BUILD_AND_RUN.bat`
4. **Your progress is preserved** - it will resume from where it stopped

The new version is 100% compatible with progress files from the old version.

## Troubleshooting

### "Session keeps restarting"
- **Cause:** Age verification not working properly
- **Solution:** Check browser window, may need to click buttons manually
- **Note:** After manual click, it should continue automatically

### "Maximum consecutive failures reached"
- **Cause:** Something is preventing successful downloads (network, site down, etc.)
- **Solution:** Wait 10-15 minutes, then restart application (resets failure counter)

### "Browser window disappeared"
- **Cause:** Accidentally closed browser window
- **Solution:** Click "Stop", then "Start Download" - browser will reopen

---

## Ready to Use!

The enhanced version is **built and ready**:

```cmd
cd C:\Development\JaxSun.Ideas\tools\EpsteinDownloader
BUILD_AND_RUN.bat
```

**New features:**
- ✅ Automatic session recovery
- ✅ Smart error detection
- ✅ Browser restart on failure
- ✅ 5-attempt retry limit
- ✅ Visible browser for monitoring
- ✅ Enhanced progress tracking

**Let it run for days - it will handle everything automatically!** 🚀
