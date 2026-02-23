#!/usr/bin/env python3
"""
Download missing DOJ Epstein PDFs from GeekenDev zip mirror and upload directly to R2.

Uses HTTP range requests to extract individual PDFs from the remote zip file
without downloading the entire archive. Zero local disk usage.

Usage:
  python download_to_r2.py                              # DS9, uses catalog + DB
  python download_to_r2.py --efta-list ds9_needed.txt  # Use pre-computed list (no DB needed)
  python download_to_r2.py --dataset 11                 # DS11
  python download_to_r2.py --workers 8                  # More workers
  python download_to_r2.py --max-files 100              # Stop after 100 files
  python download_to_r2.py --dry-run                    # Just show what would download

Transferable to another machine (no D: drive or database needed):
  1. Copy this script + ds9_needed_eftas.txt to the other machine
  2. pip install boto3 remotezip
  3. python download_to_r2.py --efta-list ds9_needed_eftas.txt --workers 8
"""

import argparse
import os
import re
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
import psycopg2
from remotezip import RemoteZip

# --- Configuration ---
CATALOG_FILE = Path(__file__).parent / "doj_catalog.txt"
PROGRESS_DIR = Path(__file__).parent
DB_CONN = "host=localhost dbname=epstein_documents user=epstein_user password=epstein_secure_pw_2024"

# GeekenDev mirror URLs (zip files with range request support)
ZIP_URLS = {
    9: "https://doj-files.geeken.dev/doj_zips/original_archives/DataSet%209.zip",
    11: "https://doj-files.geeken.dev/doj_zips/original_archives/DataSet%2011.zip",
}

R2_ENDPOINT = "https://f8370fa3403bc68c2a46a3ad87be970d.r2.cloudflarestorage.com"
R2_ACCESS_KEY = "ae0a78c0037d7ac13df823d2e085777c"
R2_SECRET_KEY = "6aed78ea947b634aa80d78b3d7d976493c1926501eecd77e4faa0691bc85faa2"
R2_BUCKET = "epsteinfiles"

RETRY_COUNT = 3
RETRY_DELAY = 5  # seconds


def load_catalog_eftas(dataset_num):
    """Load EFTA numbers from the DOJ catalog for this dataset."""
    eftas = set()
    with open(CATALOG_FILE, "r") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 3 and parts[1] == str(dataset_num):
                eftas.add(parts[0])
    return eftas


def load_db_eftas():
    """Load EFTA numbers already in the PostgreSQL database."""
    eftas = set()
    try:
        conn = psycopg2.connect(DB_CONN)
        cur = conn.cursor()
        cur.execute("SELECT efta_number FROM documents WHERE efta_number IS NOT NULL")
        for row in cur:
            eftas.add(row[0])
        cur.close()
        conn.close()
    except Exception as e:
        print(f"  WARNING: Could not connect to database: {e}")
        print(f"  Proceeding without DB filter")
    return eftas


def load_progress(dataset_num):
    """Load set of already-uploaded EFTAs."""
    progress_file = PROGRESS_DIR / f"r2_upload_progress_ds{dataset_num}.txt"
    if progress_file.exists():
        with open(progress_file, "r") as f:
            return set(line.strip() for line in f if line.strip())
    return set()


# Thread-safe progress writer
_progress_lock = threading.Lock()


def save_progress(dataset_num, efta):
    """Append a completed EFTA to progress file (thread-safe)."""
    progress_file = PROGRESS_DIR / f"r2_upload_progress_ds{dataset_num}.txt"
    with _progress_lock:
        with open(progress_file, "a") as f:
            f.write(f"{efta}\n")


def save_failure(dataset_num, efta, error):
    """Log a failed download (thread-safe)."""
    failure_file = PROGRESS_DIR / f"r2_upload_failures_ds{dataset_num}.txt"
    with _progress_lock:
        with open(failure_file, "a") as f:
            f.write(f"{efta}\t{error}\n")


def get_r2_existing(s3_client, dataset_num):
    """List all EFTAs already in R2 for this dataset."""
    prefix = f"DataSet_{dataset_num}/"
    existing = set()
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=R2_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            fname = obj["Key"].split("/")[-1]
            if fname.startswith("EFTA") and fname.endswith(".pdf"):
                existing.add(fname[:-4])  # strip .pdf
    return existing


def get_zip_file_index(zip_url):
    """Open remote zip and build index of EFTA -> zip entry name."""
    print(f"  Reading zip directory (via HTTP range requests)...", flush=True)
    index = {}
    with RemoteZip(zip_url) as rz:
        for name in rz.namelist():
            # Match EFTA PDFs in IMAGES folder
            match = re.search(r"(EFTA\d{8,11})\.pdf$", name)
            if match:
                efta = match.group(1)
                index[efta] = name
    print(f"  Found {len(index)} PDFs in zip", flush=True)
    return index


def upload_to_r2_worker(s3_client, dataset_num, efta, data):
    """Upload a single PDF to R2. Returns (efta, success, size, error)."""
    try:
        r2_key = f"DataSet_{dataset_num}/{efta}.pdf"
        s3_client.put_object(
            Bucket=R2_BUCKET,
            Key=r2_key,
            Body=data,
            ContentType="application/pdf",
        )
        save_progress(dataset_num, efta)
        return (efta, True, len(data), None)
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)[:80]}"
        save_failure(dataset_num, efta, error_msg)
        return (efta, False, 0, error_msg)


def main():
    parser = argparse.ArgumentParser(description="Download DOJ PDFs to R2 via remote zip extraction")
    parser.add_argument("--dataset", type=int, default=9, help="Dataset number (default: 9)")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent workers (default: 4)")
    parser.add_argument("--max-files", type=int, default=0, help="Max files to download (0=all)")
    parser.add_argument("--dry-run", action="store_true", help="Just show counts, don't download")
    parser.add_argument("--skip-db", action="store_true", help="Skip database check")
    parser.add_argument("--efta-list", type=str, default=None,
                        help="Pre-computed list of EFTAs to download (one per line). "
                             "Skips catalog and DB lookup — use on machines without DB access.")
    args = parser.parse_args()

    ds = args.dataset
    print(f"{'=' * 70}")
    print(f"  Remote Zip -> R2 Pipeline (Dataset {ds})")
    print(f"{'=' * 70}")

    zip_url = ZIP_URLS.get(ds)
    if not zip_url:
        print(f"  ERROR: No zip URL configured for dataset {ds}")
        sys.exit(1)

    # Initialise R2 client early — needed for the R2 check step
    s3_client = boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        region_name="auto",
    )

    # Step 1: Build zip index
    print(f"\n[1/5] Building zip file index...")
    zip_index = get_zip_file_index(zip_url)

    # Step 2: Load the target EFTA list (pre-computed file or catalog)
    if args.efta_list:
        print(f"\n[2/5] Loading pre-computed EFTA list from {args.efta_list}...")
        with open(args.efta_list) as f:
            target_eftas = set(line.strip() for line in f if line.strip())
        print(f"  EFTAs in list: {len(target_eftas)}")
        print(f"\n[3/5] Skipping database (using pre-computed list)")
    else:
        print(f"\n[2/5] Loading catalog...")
        catalog_eftas = load_catalog_eftas(ds)
        print(f"  Catalog EFTAs: {len(catalog_eftas)}")
        if not args.skip_db:
            print(f"\n[3/5] Loading database...")
            db_eftas = load_db_eftas()
            print(f"  Database EFTAs: {len(db_eftas)}")
        else:
            print(f"\n[3/5] Skipping database check")
            db_eftas = set()
        target_eftas = (catalog_eftas & set(zip_index.keys())) - db_eftas

    # Step 4: Check R2 — find what's already there and mark it complete
    print(f"\n[4/5] Checking R2 for already-uploaded files...")
    r2_existing = get_r2_existing(s3_client, ds)
    print(f"  Found in R2: {len(r2_existing)}")

    # Load local progress file
    completed = load_progress(ds)
    print(f"  In local progress file: {len(completed)}")

    # Any file in R2 but not yet in progress file → mark it complete now
    newly_marked = r2_existing - completed
    if newly_marked:
        print(f"  Marking {len(newly_marked)} R2 files as complete in progress file...")
        with _progress_lock:
            progress_file = PROGRESS_DIR / f"r2_upload_progress_ds{ds}.txt"
            with open(progress_file, "a") as f:
                for efta in sorted(newly_marked):
                    f.write(f"{efta}\n")
        completed = completed | newly_marked

    # Final set: target EFTAs not yet confirmed in R2
    all_needed = target_eftas - completed

    print(f"\n  Summary:")
    print(f"    Target EFTAs:      {len(target_eftas)}")
    print(f"    Already in R2:     {len(r2_existing)}")
    print(f"    To upload:         {len(all_needed)}")

    if not all_needed:
        print("\n  All files already uploaded!")
        return

    # Sort for deterministic ordering
    sorted_needed = sorted(all_needed)

    if args.max_files:
        sorted_needed = sorted_needed[:args.max_files]
        print(f"    Limited to:        {len(sorted_needed)}")

    if args.dry_run:
        print(f"\n  DRY RUN - would upload {len(sorted_needed)} files")
        for efta in sorted_needed[:20]:
            print(f"    {efta} -> {zip_index[efta]}")
        if len(sorted_needed) > 20:
            print(f"    ... and {len(sorted_needed) - 20} more")
        return

    # Step 5: Extract and upload
    # Strategy: single RemoteZip connection reads files sequentially,
    # R2 uploads are pipelined to a thread pool for concurrency.
    print(f"\n[5/5] Extracting and uploading ({args.workers} upload workers)...")

    stats = {"uploaded": 0, "failed": 0, "skipped": 0, "bytes": 0}
    start_time = time.time()
    total = len(sorted_needed)

    with ThreadPoolExecutor(max_workers=args.workers) as upload_pool:
        pending_futures = []

        # Open zip once, read files sequentially
        with RemoteZip(zip_url) as rz:
            for i, efta in enumerate(sorted_needed, 1):
                zip_entry = zip_index[efta]

                try:
                    data = rz.read(zip_entry)
                except Exception as e:
                    stats["failed"] += 1
                    save_failure(ds, efta, f"read_error: {type(e).__name__}")
                    continue

                # Validate PDF
                if not data or len(data) < 100:
                    stats["skipped"] += 1
                    save_failure(ds, efta, f"too_small_{len(data) if data else 0}b")
                    continue

                if data[:5] != b"%PDF-":
                    stats["skipped"] += 1
                    save_failure(ds, efta, "not_pdf")
                    continue

                # Submit R2 upload to thread pool (non-blocking)
                future = upload_pool.submit(upload_to_r2_worker, s3_client, ds, efta, data)
                pending_futures.append(future)

                # Collect completed uploads periodically
                if len(pending_futures) >= args.workers * 2:
                    done = [f for f in pending_futures if f.done()]
                    for f in done:
                        _, success, size, _ = f.result()
                        if success:
                            stats["uploaded"] += 1
                            stats["bytes"] += size
                        else:
                            stats["failed"] += 1
                        pending_futures.remove(f)

                # Progress every 100 files
                if i % 100 == 0 or i == total:
                    elapsed = time.time() - start_time
                    rate = stats["uploaded"] / elapsed * 60 if elapsed > 0 else 0
                    mb = stats["bytes"] / (1024 * 1024)
                    eta_min = (total - i) / max(rate, 0.1) if rate > 0 else 0
                    print(
                        f"  [{i}/{total}] "
                        f"OK: {stats['uploaded']} ({mb:.0f} MB) | "
                        f"Fail: {stats['failed']} | "
                        f"Skip: {stats['skipped']} | "
                        f"Rate: {rate:.0f}/min | "
                        f"ETA: {eta_min:.0f} min",
                        flush=True,
                    )

        # Wait for remaining uploads
        print(f"  Waiting for {len(pending_futures)} pending uploads...", flush=True)
        for f in as_completed(pending_futures):
            _, success, size, _ = f.result()
            if success:
                stats["uploaded"] += 1
                stats["bytes"] += size
            else:
                stats["failed"] += 1

    # Final report
    elapsed = time.time() - start_time
    print(f"\n{'=' * 70}")
    print(f"  COMPLETE - Dataset {ds}")
    print(f"{'=' * 70}")
    print(f"  Uploaded:      {stats['uploaded']}")
    print(f"  Failed:        {stats['failed']}")
    print(f"  Data:          {stats['bytes'] / (1024**3):.2f} GiB")
    print(f"  Elapsed:       {elapsed / 60:.1f} min")
    if stats["uploaded"] > 0:
        print(f"  Avg rate:      {stats['uploaded'] / elapsed * 60:.0f} files/min")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
