using System.Text;
using System.IO.Compression;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;
using Newtonsoft.Json;

namespace EpsteinDownloader;

public partial class MainForm : Form
{
    private WebView2? webView;
    private TextBox? progressTextBox;
    private Button? startButton;
    private Button? stopButton;
    private Label? statusLabel;
    private ProgressBar? progressBar;

    private readonly string outputDir = Path.Combine(Directory.GetCurrentDirectory(), "epstein_files", "DataSet_9");
    private readonly string zipDir = Path.Combine(Directory.GetCurrentDirectory(), "epstein_files", "DataSet_9", "zipped");
    private readonly string urlListFile = "actual_download_urls.txt";
    private readonly string progressFile = "download_progress.json";
    private readonly int datasetNum = 9;
    private const int FilesPerZip = 1000;

    private CancellationTokenSource? cancellationTokenSource;
    private List<FileDownloadInfo> filesToDownload = new();
    private DownloadProgress downloadProgress = new();
    private bool ageVerificationComplete = false;
    private int consecutiveFailures = 0;
    private const int MaxConsecutiveFailures = 5;
    private List<string> pendingZipFiles = new();
    private int currentZipBatch = 0;

    public MainForm()
    {
        InitializeComponent();
        InitializeAsync();
    }

    private async void InitializeAsync()
    {
        Directory.CreateDirectory(outputDir);
        Directory.CreateDirectory(zipDir);
        LoadProgress();
        LoadZipProgress();
        await InitializeWebView();
    }

    private void InitializeComponent()
    {
        this.Text = "Dataset 9 Epstein Files Downloader";
        this.Size = new Size(1000, 700);
        this.StartPosition = FormStartPosition.CenterScreen;

        // Status Label
        statusLabel = new Label
        {
            Text = "Ready to download",
            Location = new Point(20, 20),
            Size = new Size(960, 30),
            Font = new Font("Segoe UI", 12, FontStyle.Bold)
        };

        // Progress Bar
        progressBar = new ProgressBar
        {
            Location = new Point(20, 60),
            Size = new Size(960, 30),
            Style = ProgressBarStyle.Continuous
        };

        // Progress TextBox
        progressTextBox = new TextBox
        {
            Location = new Point(20, 100),
            Size = new Size(960, 200),
            Multiline = true,
            ScrollBars = ScrollBars.Vertical,
            ReadOnly = true,
            Font = new Font("Consolas", 9)
        };

        // WebView2 for age verification
        webView = new WebView2
        {
            Location = new Point(20, 310),
            Size = new Size(960, 300),
            Visible = false // Hidden until needed
        };

        // Start Button
        startButton = new Button
        {
            Text = "Start Download",
            Location = new Point(20, 620),
            Size = new Size(150, 40),
            Font = new Font("Segoe UI", 10, FontStyle.Bold)
        };
        startButton.Click += StartButton_Click;

        // Stop Button
        stopButton = new Button
        {
            Text = "Stop",
            Location = new Point(180, 620),
            Size = new Size(150, 40),
            Font = new Font("Segoe UI", 10, FontStyle.Bold),
            Enabled = false
        };
        stopButton.Click += StopButton_Click;

        // Add controls
        this.Controls.Add(statusLabel);
        this.Controls.Add(progressBar);
        this.Controls.Add(progressTextBox);
        this.Controls.Add(webView);
        this.Controls.Add(startButton);
        this.Controls.Add(stopButton);
    }

    private async Task InitializeWebView()
    {
        try
        {
            var env = await CoreWebView2Environment.CreateAsync(null, Path.Combine(Path.GetTempPath(), "EpsteinDownloader"));
            await webView!.EnsureCoreWebView2Async(env);

            // Enable JavaScript
            webView.CoreWebView2.Settings.IsScriptEnabled = true;

            Log("WebView2 initialized successfully");
        }
        catch (Exception ex)
        {
            Log($"ERROR: Failed to initialize WebView2: {ex.Message}");
            MessageBox.Show($"Failed to initialize browser component:\n{ex.Message}\n\nPlease install WebView2 Runtime.",
                "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private async void StartButton_Click(object? sender, EventArgs e)
    {
        startButton!.Enabled = false;
        stopButton!.Enabled = true;

        cancellationTokenSource = new CancellationTokenSource();

        try
        {
            // Step 1: Load URL list
            await LoadUrlListAsync();

            // Step 2: Handle age verification
            await HandleAgeVerificationAsync();

            // Step 3: Download files
            await DownloadFilesAsync(cancellationTokenSource.Token);
        }
        catch (OperationCanceledException)
        {
            Log("Download stopped by user");
            UpdateStatus("Stopped");
        }
        catch (Exception ex)
        {
            Log($"ERROR: {ex.Message}");
            MessageBox.Show($"Error: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        finally
        {
            startButton.Enabled = true;
            stopButton.Enabled = false;
        }
    }

    private void StopButton_Click(object? sender, EventArgs e)
    {
        cancellationTokenSource?.Cancel();
        Log("Stopping download...");
    }

    private async Task LoadUrlListAsync()
    {
        UpdateStatus("Loading URL list...");
        Log("Step 1: Loading actual file list (scraped from Justice.gov)");

        var urlListPath = Path.Combine(outputDir, urlListFile);

        // Check if file exists
        if (!File.Exists(urlListPath))
        {
            Log("Downloading URL list from Archive.org...");
            await DownloadUrlListAsync(urlListPath);
        }
        else
        {
            Log($"URL list found: {urlListPath}");
        }

        // Parse URLs
        Log("Parsing URLs...");
        var lines = await File.ReadAllLinesAsync(urlListPath);

        filesToDownload.Clear();
        foreach (var line in lines)
        {
            if (string.IsNullOrWhiteSpace(line) || !line.StartsWith("http"))
                continue;

            var filename = Path.GetFileName(new Uri(line).AbsolutePath);
            if (filename.EndsWith(".pdf", StringComparison.OrdinalIgnoreCase))
            {
                filesToDownload.Add(new FileDownloadInfo
                {
                    Filename = filename,
                    Url = line
                });
            }
        }

        Log($"Found {filesToDownload.Count:N0} PDF files to download");

        // Remove already downloaded
        var existingFiles = Directory.GetFiles(outputDir, "*.pdf")
            .Select(Path.GetFileName)
            .ToHashSet();

        var toDownload = filesToDownload.Where(f => !existingFiles.Contains(f.Filename)).ToList();
        var alreadyDownloaded = filesToDownload.Count - toDownload.Count;

        filesToDownload = toDownload;

        Log($"Already downloaded: {alreadyDownloaded:N0} files");
        Log($"Remaining to download: {filesToDownload.Count:N0} files");
    }

    private async Task DownloadUrlListAsync(string outputPath)
    {
        const string archiveUrl = "https://archive.org/download/dataset9_url_list/dataset9_url_list.txt";

        using var client = new HttpClient();
        client.Timeout = TimeSpan.FromMinutes(10);

        var response = await client.GetAsync(archiveUrl, HttpCompletionOption.ResponseHeadersRead);
        response.EnsureSuccessStatusCode();

        var totalBytes = response.Content.Headers.ContentLength ?? 0;
        Log($"Downloading {totalBytes / 1024 / 1024:F1} MB...");

        await using var stream = await response.Content.ReadAsStreamAsync();
        await using var fileStream = File.Create(outputPath);

        var buffer = new byte[8192];
        long bytesRead = 0;
        int read;

        while ((read = await stream.ReadAsync(buffer)) > 0)
        {
            await fileStream.WriteAsync(buffer.AsMemory(0, read));
            bytesRead += read;

            if (totalBytes > 0 && bytesRead % (1024 * 1024) == 0)
            {
                var percent = (bytesRead * 100.0 / totalBytes);
                UpdateProgress((int)percent, $"Downloading URL list: {percent:F1}%");
            }
        }

        Log($"URL list downloaded: {outputPath}");
    }

    private async Task HandleAgeVerificationAsync()
    {
        if (ageVerificationComplete)
        {
            Log("Age verification already complete");
            return;
        }

        UpdateStatus("Handling age verification...");
        Log("Step 2: Age verification");
        Log($"[BROWSER] Opening browser and navigating to site...");

        // Show WebView - keep it visible for verification
        webView!.Visible = true;
        webView.BringToFront();

        // Navigate to age verification page
        Log("[NAVIGATE] Going to age verification page...");
        webView.CoreWebView2.Navigate("https://www.justice.gov/age-verify");

        Log("[WAIT] Waiting for page to load...");
        await Task.Delay(4000);

        Log("");
        Log(new string('=', 80));
        Log("AGE VERIFICATION - AUTO CLICKING");
        Log(new string('=', 80));

        // Step 1: Click "I am not a robot" button
        Log("[STEP 1] Looking for 'I am not a robot' button...");
        var robotButtonClicked = await ClickButtonAsync("document.querySelector('input[value=\"I am not a robot\"]')");

        if (robotButtonClicked)
        {
            Log("[SUCCESS] Robot button clicked!");
            await Task.Delay(4000);
        }
        else
        {
            Log("[WARN] Robot button not found - may already be clicked");
        }

        // Step 2: Click age verification button
        Log("");
        Log("[STEP 2] Looking for 'Yes' (18+) button...");
        var ageButtonClicked = await ClickButtonAsync("document.getElementById('age-button-yes')");

        if (ageButtonClicked)
        {
            Log("[SUCCESS] Age verification button clicked!");
            Log(new string('=', 80));
            await Task.Delay(3000);
            ageVerificationComplete = true;

            // Keep WebView visible for monitoring
            Log("[INFO] Age verification completed - cookies set");
            Log("[INFO] Browser will remain visible for monitoring");
        }
        else
        {
            Log("[ERROR] Age button not found!");
            throw new Exception("Failed to complete age verification. Please click the buttons manually.");
        }
    }

    private async Task<bool> ClickButtonAsync(string jsSelector)
    {
        try
        {
            var script = $@"
                (function() {{
                    var button = {jsSelector};
                    if (button && button.offsetParent !== null) {{
                        button.click();
                        return true;
                    }}
                    return false;
                }})();
            ";

            var result = await webView!.CoreWebView2.ExecuteScriptAsync(script);
            return result == "true";
        }
        catch
        {
            return false;
        }
    }

    private async Task DownloadFilesAsync(CancellationToken cancellationToken)
    {
        UpdateStatus("Downloading files...");
        Log($"Step 3: Downloading {filesToDownload.Count:N0} files");

        while (downloadProgress.LastProcessedIndex < filesToDownload.Count && consecutiveFailures < MaxConsecutiveFailures)
        {
            cancellationToken.ThrowIfCancellationRequested();

            try
            {
                // Attempt download batch
                await DownloadBatchAsync(cancellationToken);

                // If we get here, batch was successful - reset failure counter
                consecutiveFailures = 0;
            }
            catch (DownloadSessionException ex)
            {
                consecutiveFailures++;
                Log($"[SESSION ERROR] {ex.Message}");
                Log($"[RETRY] Consecutive failures: {consecutiveFailures}/{MaxConsecutiveFailures}");

                if (consecutiveFailures >= MaxConsecutiveFailures)
                {
                    Log($"[FATAL] Maximum consecutive failures reached. Stopping.");
                    UpdateStatus($"Failed after {MaxConsecutiveFailures} retry attempts");
                    break;
                }

                // Close browser and restart age verification
                Log($"[RESTART] Closing browser and restarting session...");
                await Task.Delay(2000, cancellationToken); // Wait before retry
                ageVerificationComplete = false;
                await HandleAgeVerificationAsync();
            }
        }

        if (downloadProgress.LastProcessedIndex >= filesToDownload.Count)
        {
            // Zip any remaining files
            if (pendingZipFiles.Count > 0)
            {
                Log($"[ZIP] Creating final batch with {pendingZipFiles.Count} remaining files...");
                await CreateZipBatchAsync(cancellationToken);
            }

            Log($"\n{'=',80}");
            Log("Download Complete!");
            Log($"  Success: {downloadProgress.SuccessCount:N0}");
            Log($"  Errors: {downloadProgress.ErrorCount:N0}");
            Log($"  Zip batches created: {currentZipBatch}");
            Log($"  Zip location: {zipDir}");
            Log($"  Individual files location: {outputDir}");
            Log($"{'=',80}");
            UpdateStatus("Download complete!");
        }

        SaveProgress();
    }

    private async Task DownloadBatchAsync(CancellationToken cancellationToken)
    {
        var httpHandler = new HttpClientHandler
        {
            UseCookies = true,
            CookieContainer = new System.Net.CookieContainer()
        };

        // Get cookies from WebView
        var cookies = await webView!.CoreWebView2.CookieManager.GetCookiesAsync("https://www.justice.gov");
        foreach (var cookie in cookies)
        {
            httpHandler.CookieContainer.Add(new Uri("https://www.justice.gov"),
                new System.Net.Cookie(cookie.Name, cookie.Value, cookie.Path, cookie.Domain));
        }

        using var client = new HttpClient(httpHandler)
        {
            Timeout = TimeSpan.FromMinutes(2)
        };

        client.DefaultRequestHeaders.Add("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36");

        var startTime = DateTime.Now;
        var batchStartIndex = downloadProgress.LastProcessedIndex;
        var errorStreak = 0;
        const int MaxErrorStreak = 10; // Consecutive errors before restarting session

        for (int i = downloadProgress.LastProcessedIndex; i < filesToDownload.Count; i++)
        {
            cancellationToken.ThrowIfCancellationRequested();

            var file = filesToDownload[i];
            var filePath = Path.Combine(outputDir, file.Filename);
            var fileNumber = i + 1;

            // Skip if already exists and is valid PDF
            if (File.Exists(filePath) && IsValidPdf(filePath))
            {
                if (fileNumber % 100 == 0)
                    Log($"[{fileNumber}/{filesToDownload.Count}] [SKIP] {file.Filename}");
                continue;
            }

            try
            {
                var response = await client.GetAsync(file.Url, cancellationToken);

                if (response.IsSuccessStatusCode)
                {
                    var bytes = await response.Content.ReadAsByteArrayAsync(cancellationToken);

                    // Check if it's a PDF
                    if (bytes.Length > 4 && bytes[0] == 0x25 && bytes[1] == 0x50 && bytes[2] == 0x44 && bytes[3] == 0x46) // %PDF
                    {
                        await File.WriteAllBytesAsync(filePath, bytes, cancellationToken);
                        downloadProgress.SuccessCount++;
                        errorStreak = 0; // Reset error streak on success

                        // Add to pending zip list
                        pendingZipFiles.Add(filePath);

                        Log($"[{fileNumber}/{filesToDownload.Count}] [OK] {file.Filename} ({bytes.Length:N0} bytes)");

                        // Check if we should create a zip
                        if (pendingZipFiles.Count >= FilesPerZip)
                        {
                            await CreateZipBatchAsync(cancellationToken);
                        }
                    }
                    else
                    {
                        // Got HTML instead of PDF - likely session expired
                        downloadProgress.ErrorCount++;
                        errorStreak++;
                        Log($"[{fileNumber}/{filesToDownload.Count}] [ERROR] Not a PDF (got HTML): {file.Filename}");

                        // Check if this is an age verification page
                        var html = System.Text.Encoding.UTF8.GetString(bytes);
                        if (html.Contains("age-verify") || html.Contains("Age Verification"))
                        {
                            Log($"[SESSION EXPIRED] Age verification required again");
                            throw new DownloadSessionException("Session expired - age verification required");
                        }

                        // If we have many consecutive errors, session might be broken
                        if (errorStreak >= MaxErrorStreak)
                        {
                            Log($"[SESSION ERROR] {errorStreak} consecutive errors - session likely expired");
                            throw new DownloadSessionException($"{errorStreak} consecutive errors");
                        }
                    }
                }
                else if (response.StatusCode == System.Net.HttpStatusCode.NotFound)
                {
                    downloadProgress.ErrorCount++;
                    // 404 is expected for many files, don't count as error streak
                    if (fileNumber % 100 == 0)
                        Log($"[{fileNumber}/{filesToDownload.Count}] [404] {file.Filename}");
                }
                else if (response.StatusCode == System.Net.HttpStatusCode.Forbidden ||
                         response.StatusCode == System.Net.HttpStatusCode.Unauthorized)
                {
                    // Authentication error - restart session
                    downloadProgress.ErrorCount++;
                    Log($"[{fileNumber}/{filesToDownload.Count}] [AUTH ERROR] HTTP {(int)response.StatusCode}");
                    throw new DownloadSessionException($"Authentication error: {response.StatusCode}");
                }
                else
                {
                    downloadProgress.ErrorCount++;
                    errorStreak++;
                    Log($"[{fileNumber}/{filesToDownload.Count}] [ERROR] HTTP {(int)response.StatusCode}: {file.Filename}");
                }
            }
            catch (DownloadSessionException)
            {
                // Re-throw session exceptions to trigger restart
                throw;
            }
            catch (Exception ex) when (!(ex is OperationCanceledException))
            {
                downloadProgress.ErrorCount++;
                if (fileNumber % 100 == 0)
                    Log($"[{fileNumber}/{filesToDownload.Count}] [ERROR] {ex.Message}");
            }

            // Update progress
            downloadProgress.LastProcessedIndex = i;
            downloadProgress.LastUpdate = DateTime.Now;

            var percent = (int)((fileNumber * 100.0) / filesToDownload.Count);
            UpdateProgress(percent, $"Downloaded: {downloadProgress.SuccessCount:N0} | Errors: {downloadProgress.ErrorCount:N0} | Progress: {fileNumber:N0}/{filesToDownload.Count:N0}");

            // Save progress every 100 files
            if (fileNumber % 100 == 0)
            {
                SaveProgress();

                var elapsed = DateTime.Now - startTime;
                var filesProcessed = fileNumber - batchStartIndex;
                var rate = filesProcessed / elapsed.TotalSeconds;
                var remaining = filesToDownload.Count - fileNumber;
                var eta = rate > 0 ? remaining / rate : 0;

                Log($"[PROGRESS] Rate: {rate:F1} files/sec | ETA: {TimeSpan.FromSeconds(eta):hh\\:mm\\:ss} | Failures: {consecutiveFailures}/{MaxConsecutiveFailures}");
            }

            // Rate limiting
            await Task.Delay(300, cancellationToken);
        }

        // Batch completed successfully
        SaveProgress();
    }

    private bool IsValidPdf(string filePath)
    {
        try
        {
            using var fs = File.OpenRead(filePath);
            var buffer = new byte[4];
            fs.Read(buffer, 0, 4);
            return buffer[0] == 0x25 && buffer[1] == 0x50 && buffer[2] == 0x44 && buffer[3] == 0x46; // %PDF
        }
        catch
        {
            return false;
        }
    }

    private void LoadProgress()
    {
        var progressPath = Path.Combine(outputDir, progressFile);
        if (File.Exists(progressPath))
        {
            try
            {
                var json = File.ReadAllText(progressPath);
                downloadProgress = JsonConvert.DeserializeObject<DownloadProgress>(json) ?? new DownloadProgress();
                Log($"Loaded progress: Last index {downloadProgress.LastProcessedIndex}");
            }
            catch
            {
                downloadProgress = new DownloadProgress();
            }
        }
    }

    private void SaveProgress()
    {
        var progressPath = Path.Combine(outputDir, progressFile);
        try
        {
            var json = JsonConvert.SerializeObject(downloadProgress, Formatting.Indented);
            File.WriteAllText(progressPath, json);
        }
        catch (Exception ex)
        {
            Log($"Warning: Could not save progress: {ex.Message}");
        }
    }

    private void LoadZipProgress()
    {
        // Count existing zip files to determine current batch number
        var existingZips = Directory.GetFiles(zipDir, "dataset9_batch_*.zip");
        if (existingZips.Length > 0)
        {
            var maxBatch = existingZips
                .Select(Path.GetFileNameWithoutExtension)
                .Select(name => int.TryParse(name.Replace("dataset9_batch_", ""), out int num) ? num : 0)
                .Max();
            currentZipBatch = maxBatch;
            Log($"Found {existingZips.Length} existing zip files. Starting from batch {currentZipBatch + 1}");
        }
    }

    private async Task CreateZipBatchAsync(CancellationToken cancellationToken)
    {
        if (pendingZipFiles.Count == 0)
            return;

        currentZipBatch++;
        var zipFileName = $"dataset9_batch_{currentZipBatch:D4}.zip";
        var zipPath = Path.Combine(zipDir, zipFileName);

        Log("");
        Log(new string('=', 80));
        Log($"[ZIP] Creating {zipFileName} with {pendingZipFiles.Count} files...");
        UpdateStatus($"Creating zip batch {currentZipBatch}...");

        try
        {
            // Create zip file
            using (var zipArchive = ZipFile.Open(zipPath, ZipArchiveMode.Create))
            {
                for (int i = 0; i < pendingZipFiles.Count; i++)
                {
                    cancellationToken.ThrowIfCancellationRequested();

                    var filePath = pendingZipFiles[i];
                    if (File.Exists(filePath))
                    {
                        var entryName = Path.GetFileName(filePath);
                        zipArchive.CreateEntryFromFile(filePath, entryName, CompressionLevel.Optimal);

                        if ((i + 1) % 100 == 0)
                        {
                            Log($"[ZIP] Progress: {i + 1}/{pendingZipFiles.Count} files added");
                        }
                    }
                }
            }

            var zipSize = new FileInfo(zipPath).Length / 1024 / 1024;
            Log($"[ZIP] Created: {zipFileName} ({zipSize} MB)");

            // Delete original files after successful zip
            Log($"[ZIP] Removing {pendingZipFiles.Count} original files...");
            foreach (var filePath in pendingZipFiles)
            {
                try
                {
                    if (File.Exists(filePath))
                        File.Delete(filePath);
                }
                catch (Exception ex)
                {
                    Log($"[ZIP] Warning: Could not delete {Path.GetFileName(filePath)}: {ex.Message}");
                }
            }

            Log($"[ZIP] Batch {currentZipBatch} complete!");
            Log(new string('=', 80));
            Log("");

            // Clear pending files
            pendingZipFiles.Clear();

            UpdateStatus($"Zip batch {currentZipBatch} created - resuming downloads...");
        }
        catch (Exception ex)
        {
            Log($"[ZIP ERROR] Failed to create zip: {ex.Message}");
            Log($"[ZIP] Files will remain unzipped");
            // Don't clear pending files - they'll stay as individual files
        }
    }

    private void Log(string message)
    {
        if (progressTextBox?.InvokeRequired == true)
        {
            progressTextBox.Invoke(() => Log(message));
            return;
        }

        var timestamp = DateTime.Now.ToString("HH:mm:ss");
        if (progressTextBox != null)
        {
            progressTextBox.AppendText($"[{timestamp}] {message}\r\n");
            progressTextBox.SelectionStart = progressTextBox.Text.Length;
            progressTextBox.ScrollToCaret();
        }
    }

    private void UpdateStatus(string status)
    {
        if (statusLabel?.InvokeRequired == true)
        {
            statusLabel.Invoke(() => UpdateStatus(status));
            return;
        }

        statusLabel!.Text = status;
    }

    private void UpdateProgress(int percent, string? status = null)
    {
        if (progressBar?.InvokeRequired == true)
        {
            progressBar.Invoke(() => UpdateProgress(percent, status));
            return;
        }

        progressBar!.Value = Math.Min(percent, 100);

        if (status != null)
            UpdateStatus(status);
    }
}

public class FileDownloadInfo
{
    public string Filename { get; set; } = "";
    public string Url { get; set; } = "";
}

public class DownloadProgress
{
    public int LastProcessedIndex { get; set; }
    public int SuccessCount { get; set; }
    public int ErrorCount { get; set; }
    public DateTime LastUpdate { get; set; } = DateTime.Now;
}

public class DownloadSessionException : Exception
{
    public DownloadSessionException(string message) : base(message) { }
}
