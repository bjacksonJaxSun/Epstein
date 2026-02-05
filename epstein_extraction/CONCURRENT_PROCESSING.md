# Concurrent Processing Guide

Run extraction **while files are still downloading** using the continuous processor.

## Key Features

✅ **Resume-Safe**: Automatically skips already-processed files
✅ **Download-Safe**: Waits for files to finish being written before processing
✅ **Progress Tracking**: Shows real-time progress as files arrive
✅ **Batch Processing**: Processes files in configurable batches
✅ **Auto-Recovery**: Handles interruptions gracefully

## Quick Start

### Continuous Mode (Recommended)

Runs forever, checking for new files every 60 seconds:

```bash
python continuous_processor.py --mode continuous
```

### Single-Pass Mode

Process all new files once, then exit (good for cron jobs):

```bash
python continuous_processor.py --mode once
```

## Command-Line Options

```bash
python continuous_processor.py \
    --mode continuous \           # 'continuous' or 'once'
    --interval 60 \               # Seconds between scans (default: 60)
    --batch-size 50 \             # Files per batch (default: 50)
    --directory /path/to/pdfs     # Directory to watch (optional)
```

## Examples

### Start processing while downloading

```bash
# In one terminal: start downloading
cd tools\EpsteinDownloader
python download_dataset_9_final.py

# In another terminal: start processing
cd epstein_extraction
python continuous_processor.py
```

### Fast processing (small batches, frequent scans)

```bash
python continuous_processor.py --interval 30 --batch-size 25
```

### Slow/careful processing (large batches, infrequent scans)

```bash
python continuous_processor.py --interval 300 --batch-size 100
```

### Run as background service (Linux/Mac)

```bash
nohup python continuous_processor.py > processor.log 2>&1 &
```

### Run as background service (Windows)

```powershell
Start-Process python -ArgumentList "continuous_processor.py" -WindowStyle Hidden
```

## How It Works

### 1. Initial Scan
- Loads all already-processed files from database
- Scans directory for existing PDFs
- Identifies new files to process

### 2. File Readiness Check
Before processing each file, the system:
- Waits 2 seconds and checks if file size changes
- Verifies file can be opened (not locked by download process)
- Skips files that are still being written

### 3. Batch Processing
- Processes new files in configurable batches
- Updates database after each file
- Marks files as processed to avoid reprocessing

### 4. Continuous Monitoring
- Sleeps for configured interval (default: 60s)
- Re-scans directory for new files
- Repeats process until stopped (Ctrl+C)

## Progress Monitoring

### Real-Time Progress

The processor shows progress every scan:

```
============================================================
CONTINUOUS PROCESSING PROGRESS
============================================================
Time:                  2026-02-03T10:30:45
Total Files Downloaded: 2847
Files Processed:        2847
Files Pending:          0
Progress:               100.00%
------------------------------------------------------------
Database Documents:     2847
Database People:        1243
Database Events:        567
Database Relationships: 892
============================================================
```

### Query Progress Programmatically

```python
from continuous_processor import ContinuousProcessor

processor = ContinuousProcessor()
report = processor.get_progress_report()

print(f"Progress: {report['progress_percentage']:.1f}%")
print(f"Pending: {report['files_pending']} files")
```

## Interruption Handling

### Safe to Stop Anytime

Press **Ctrl+C** to stop gracefully:
- Current file finishes processing
- Database commits all changes
- Can resume later without data loss

### Resume After Interruption

Simply restart the processor:
```bash
python continuous_processor.py
```

It will automatically:
- Load list of processed files from database
- Skip already-processed files
- Continue with new/pending files

## Performance Tuning

### For Fast Processing
```bash
# Aggressive: check every 15 seconds, small batches
python continuous_processor.py --interval 15 --batch-size 10
```

### For Resource-Constrained Systems
```bash
# Conservative: check every 5 minutes, large batches
python continuous_processor.py --interval 300 --batch-size 200
```

### Optimal Settings (Recommended)
```bash
# Balanced: check every minute, medium batches
python continuous_processor.py --interval 60 --batch-size 50
```

## Common Scenarios

### Scenario 1: Start fresh download + processing

```bash
# Terminal 1: Download
python download_dataset_9_final.py

# Terminal 2: Process (wait 1-2 minutes for first files)
cd epstein_extraction
python continuous_processor.py --interval 30
```

### Scenario 2: Resume interrupted download + processing

```bash
# Terminal 1: Resume download
python download_dataset_9_final.py

# Terminal 2: Resume processing (auto-skips already processed)
cd epstein_extraction
python continuous_processor.py
```

### Scenario 3: Process existing files, then watch for new ones

```bash
# Will process all existing files first, then continue monitoring
python continuous_processor.py --batch-size 100
```

### Scenario 4: Scheduled batch processing (cron job)

```bash
# Add to crontab (runs every hour)
0 * * * * cd /path/to/epstein_extraction && python continuous_processor.py --mode once
```

## Troubleshooting

### "File still being written" warnings

**Normal behavior** - the processor detected a file being downloaded and skipped it. It will process the file on the next scan once complete.

### Files being skipped repeatedly

Check if files are:
- Locked by another process
- Corrupted (can't be opened)
- Very large (taking long time to download)

### Processing too slow

1. Increase `--batch-size` to process more files per batch
2. Decrease `--interval` to scan more frequently
3. Enable parallel processing (modify config.py: `MAX_WORKERS=8`)

### Processing too aggressive

1. Decrease `--batch-size` to reduce memory usage
2. Increase `--interval` to scan less frequently
3. Disable OCR if not needed (config.py: `ENABLE_OCR=False`)

## Database Queries While Processing

You can query the database while processing is running:

```python
from config import SessionLocal
from models import Document, Person

db = SessionLocal()

# Check latest processed document
latest = db.query(Document).order_by(Document.created_at.desc()).first()
print(f"Latest: {latest.efta_number} at {latest.created_at}")

# Count people extracted so far
person_count = db.query(Person).count()
print(f"Total people: {person_count}")

db.close()
```

## Logs

All processing activity is logged to:
```
extraction_output/logs/extraction_YYYY-MM-DD.log
```

View logs in real-time:
```bash
# Windows
Get-Content extraction_output\logs\extraction_2026-02-03.log -Wait

# Linux/Mac
tail -f extraction_output/logs/extraction_2026-02-03.log
```

## Integration with Download Scripts

The continuous processor works seamlessly with any download script:

```bash
# Dataset 9 (currently downloading)
python download_dataset_9_final.py

# Dataset 10
python download_dataset_10_final.py

# Dataset 11
python download_dataset_11_final.py
```

Just point the processor to the correct directory:
```bash
python continuous_processor.py --directory ../epstein_files/DataSet_10
```

## Best Practices

1. **Start processing early** - Begin as soon as first files arrive
2. **Monitor progress** - Check logs periodically
3. **Adjust batch size** - Based on your system's RAM
4. **Don't interrupt mid-batch** - Wait for batch to complete
5. **Run relationship building separately** - After all files processed

## Next Steps After Processing

Once all files are processed:

```bash
# Build relationships
python -c "from main import ExtractionOrchestrator; o = ExtractionOrchestrator(); o.build_relationships()"

# Deduplicate entities
python -c "from main import ExtractionOrchestrator; o = ExtractionOrchestrator(); o.deduplicate_entities()"

# Print final statistics
python -c "from main import ExtractionOrchestrator; o = ExtractionOrchestrator(); o.print_statistics()"
```
