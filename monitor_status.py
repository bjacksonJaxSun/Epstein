#!/usr/bin/env python3
"""Real-time status monitor for Dataset 9 downloader"""

import json
import time
from pathlib import Path
from datetime import datetime

output_dir = Path("epstein_files/DataSet_9")

def monitor():
    print("="*80)
    print("Dataset 9 Download Monitor - Press Ctrl+C to stop")
    print("="*80)
    print()

    last_count = 0
    start_time = time.time()

    while True:
        try:
            # Clear previous output (simple version)
            print("\n" + "="*80)
            print(f"Status at {datetime.now().strftime('%H:%M:%S')}")
            print("="*80)

            if not output_dir.exists():
                print("[WAITING] Output directory not created yet...")
                time.sleep(5)
                continue

            # Count PDFs
            pdf_files = list(output_dir.glob("*.pdf"))
            pdf_count = len(pdf_files)

            # Check progress file
            progress_file = output_dir / "download_progress.json"
            if progress_file.exists():
                with open(progress_file) as f:
                    progress = json.load(f)

                print(f"[OK] Progress file found")
                print(f"  Last processed: {progress.get('LastProcessedIndex', 0):,}")
                print(f"  Success: {progress.get('SuccessCount', 0):,}")
                print(f"  Errors: {progress.get('ErrorCount', 0):,}")
                print(f"  Last update: {progress.get('LastUpdate', 'Unknown')}")
                print()

            # Show PDF count
            print(f"[PDFs] Total downloaded: {pdf_count:,}")

            # Calculate rate
            if pdf_count > last_count:
                elapsed = time.time() - start_time
                rate = pdf_count / elapsed if elapsed > 0 else 0
                print(f"[RATE] {rate:.2f} files/second")

                # Estimate total time for 1.2M files
                if rate > 0:
                    total_seconds = 1224009 / rate
                    hours = int(total_seconds // 3600)
                    minutes = int((total_seconds % 3600) // 60)
                    print(f"[ETA] ~{hours}h {minutes}m for full download")

            last_count = pdf_count

            # Show most recent file
            if pdf_files:
                recent = max(pdf_files, key=lambda p: p.stat().st_mtime)
                size_mb = recent.stat().st_size / 1024 / 1024
                mtime = datetime.fromtimestamp(recent.stat().st_mtime).strftime('%H:%M:%S')
                print(f"\n[LATEST] {recent.name}")
                print(f"  Size: {size_mb:.1f} MB")
                print(f"  Time: {mtime}")

            # Check URL list
            url_list = output_dir / "archive_org_url_list.txt"
            if url_list.exists():
                size_mb = url_list.stat().st_size / 1024 / 1024
                print(f"\n[URL LIST] Downloaded ({size_mb:.1f} MB)")
            else:
                print(f"\n[URL LIST] Not downloaded yet")

            print()
            print("Refreshing in 10 seconds... (Ctrl+C to stop)")
            time.sleep(10)

        except KeyboardInterrupt:
            print("\n\nMonitoring stopped.")
            break
        except Exception as e:
            print(f"\n[ERROR] {e}")
            time.sleep(10)

if __name__ == '__main__':
    monitor()
