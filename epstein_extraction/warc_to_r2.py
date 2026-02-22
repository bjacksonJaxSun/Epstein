#!/usr/bin/env python3
"""
Extract PDFs from Internet Archive WARC files and upload directly to R2.

Downloads WARC files one at a time from IA, extracts PDF responses,
uploads each to Cloudflare R2, then deletes the WARC to free disk space.

Usage:
  python warc_to_r2.py                        # Process all WARC files
  python warc_to_r2.py --start 5              # Start from WARC #5
  python warc_to_r2.py --start 5 --end 7      # Process WARCs 5-7 only
  python warc_to_r2.py --dry-run              # Show what would be extracted
  python warc_to_r2.py --keep-warc            # Don't delete WARC after processing
"""

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import boto3
import psycopg2
from warcio.archiveiterator import ArchiveIterator

# --- Configuration ---
IA_BASE = "https://archive.org/download/www.justice.gov_epstein_files_DataSet_9_individual_pdf_bruteforce"
WARC_TEMPLATE = "www.justice.gov_epstein_files_DataSet_9-individual-pdfs-bruteforce-{num:05d}.warc.gz"
WARC_COUNT = 19  # 00000 through 00018
DOWNLOAD_DIR = Path("D:/Personal/Epstein/data/temp_warc")

CATALOG_FILE = Path(__file__).parent / "doj_catalog.txt"
DB_CONN = "host=localhost dbname=epstein_documents user=epstein_user password=epstein_secure_pw_2024"

R2_ENDPOINT = "https://f8370fa3403bc68c2a46a3ad87be970d.r2.cloudflarestorage.com"
R2_ACCESS_KEY = "ae0a78c0037d7ac13df823d2e085777c"
R2_SECRET_KEY = "6aed78ea947b634aa80d78b3d7d976493c1926501eecd77e4faa0691bc85faa2"
R2_BUCKET = "epsteinfiles"
R2_PREFIX = "DataSet_9"

PROGRESS_FILE = Path(__file__).parent / "warc_to_r2_progress.txt"


def load_catalog_eftas(dataset_num=9):
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
        print(f"  Proceeding without DB filter (will upload all catalog EFTAs)")
    return eftas


def load_progress():
    """Load set of already-uploaded EFTAs."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r") as f:
            return set(line.strip() for line in f if line.strip())
    return set()


def save_progress_batch(eftas):
    """Append a batch of completed EFTAs to progress file."""
    with open(PROGRESS_FILE, "a") as f:
        for efta in eftas:
            f.write(f"{efta}\n")


def download_warc(warc_filename):
    """Download a WARC file from Internet Archive using curl (supports resume)."""
    url = f"{IA_BASE}/{warc_filename}"
    local_path = DOWNLOAD_DIR / warc_filename

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    if local_path.exists():
        local_size = local_path.stat().st_size
        print(f"  WARC exists locally ({local_size / (1024**3):.2f} GiB), resuming if incomplete...")
    else:
        print(f"  Downloading {warc_filename}...")

    # Use curl with resume support
    result = subprocess.run(
        [
            "curl", "-L", "-C", "-",
            "--progress-bar",
            "-o", str(local_path),
            url,
        ],
        capture_output=False,
    )

    if result.returncode != 0:
        print(f"  ERROR: curl returned {result.returncode}")
        return None

    final_size = local_path.stat().st_size
    print(f"  Downloaded: {final_size / (1024**3):.2f} GiB")
    return local_path


def extract_and_upload(warc_path, s3_client, completed, allowed_eftas, dry_run=False):
    """Extract PDFs from WARC and upload to R2.
    Only uploads EFTAs that are in allowed_eftas (catalog minus DB)."""
    stats = {
        "total_records": 0,
        "pdfs_found": 0,
        "pdfs_uploaded": 0,
        "pdfs_skipped": 0,
        "pdfs_not_in_catalog": 0,
        "non_pdf": 0,
        "errors": 0,
        "bytes_uploaded": 0,
    }

    batch_progress = []
    batch_size = 100  # Save progress every 100 files

    print(f"  Processing {warc_path.name}...")
    start_time = time.time()

    with open(warc_path, "rb") as f:
        for record in ArchiveIterator(f):
            stats["total_records"] += 1

            # Only process HTTP responses
            if record.rec_type != "response":
                continue

            url = record.rec_headers.get_header("WARC-Target-URI")
            if not url:
                continue

            # Extract EFTA number from URL
            match = re.search(r"(EFTA\d{8,11})\.pdf", url)
            if not match:
                continue

            efta = match.group(1)

            # Only process EFTAs that are in catalog and not in DB
            if efta not in allowed_eftas:
                stats["pdfs_not_in_catalog"] += 1
                continue

            # Check content type
            http_headers = record.http_headers
            if http_headers is None:
                continue

            status = http_headers.get_statuscode()
            content_type = http_headers.get_header("Content-Type") or ""

            # Only process successful PDF responses
            if status != "200":
                stats["non_pdf"] += 1
                continue

            if "pdf" not in content_type.lower() and "octet-stream" not in content_type.lower():
                stats["non_pdf"] += 1
                continue

            # Read the content
            content = record.content_stream().read()

            # Validate it's actually a PDF
            if not content[:5] == b"%PDF-":
                stats["non_pdf"] += 1
                continue

            stats["pdfs_found"] += 1

            # Skip if already uploaded
            if efta in completed:
                stats["pdfs_skipped"] += 1
                continue

            if dry_run:
                stats["pdfs_uploaded"] += 1
                stats["bytes_uploaded"] += len(content)
                continue

            # Upload to R2
            try:
                r2_key = f"{R2_PREFIX}/{efta}.pdf"
                s3_client.put_object(
                    Bucket=R2_BUCKET,
                    Key=r2_key,
                    Body=content,
                    ContentType="application/pdf",
                )
                stats["pdfs_uploaded"] += 1
                stats["bytes_uploaded"] += len(content)
                batch_progress.append(efta)
                completed.add(efta)

                # Save progress periodically
                if len(batch_progress) >= batch_size:
                    save_progress_batch(batch_progress)
                    elapsed = time.time() - start_time
                    rate = stats["pdfs_uploaded"] / elapsed * 60
                    print(
                        f"    Uploaded: {stats['pdfs_uploaded']} | "
                        f"Skipped: {stats['pdfs_skipped']} | "
                        f"Non-PDF: {stats['non_pdf']} | "
                        f"{stats['bytes_uploaded'] / (1024**3):.2f} GiB | "
                        f"{rate:.0f}/min",
                        flush=True,
                    )
                    batch_progress = []

            except Exception as e:
                stats["errors"] += 1
                if stats["errors"] <= 5:
                    print(f"    Upload error for {efta}: {e}")

    # Save remaining progress
    if batch_progress:
        save_progress_batch(batch_progress)

    elapsed = time.time() - start_time
    rate = stats["pdfs_uploaded"] / elapsed * 60 if elapsed > 0 and stats["pdfs_uploaded"] > 0 else 0

    print(f"\n  WARC Summary:")
    print(f"    Total WARC records: {stats['total_records']}")
    print(f"    Valid PDFs found:   {stats['pdfs_found']}")
    print(f"    Uploaded to R2:     {stats['pdfs_uploaded']}")
    print(f"    Already on R2:      {stats['pdfs_skipped']}")
    print(f"    Not in catalog/DB:  {stats['pdfs_not_in_catalog']}")
    print(f"    Non-PDF responses:  {stats['non_pdf']}")
    print(f"    Upload errors:      {stats['errors']}")
    print(f"    Data uploaded:      {stats['bytes_uploaded'] / (1024**3):.2f} GiB")
    print(f"    Time:               {elapsed / 60:.1f} min")
    if rate > 0:
        print(f"    Rate:               {rate:.0f} files/min")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Extract PDFs from WARC and upload to R2")
    parser.add_argument("--start", type=int, default=0, help="Start WARC index (default: 0)")
    parser.add_argument("--end", type=int, default=WARC_COUNT - 1, help="End WARC index (default: 18)")
    parser.add_argument("--dry-run", action="store_true", help="Don't upload, just count")
    parser.add_argument("--keep-warc", action="store_true", help="Don't delete WARC after processing")
    args = parser.parse_args()

    print(f"{'=' * 70}")
    print(f"  WARC -> R2 Extractor (Dataset 9)")
    print(f"  WARCs {args.start:05d} through {args.end:05d}")
    print(f"{'=' * 70}")

    # Initialize R2 client
    s3_client = boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        region_name="auto",
    )

    # Load catalog (source of truth for what we need)
    print(f"\n  Loading DS9 catalog...")
    catalog_eftas = load_catalog_eftas(9)
    print(f"  Catalog EFTAs: {len(catalog_eftas)}")

    # Load DB (what we already have indexed)
    print(f"  Loading database EFTAs...")
    db_eftas = load_db_eftas()
    print(f"  Database EFTAs: {len(db_eftas)}")

    # Allowed = in catalog AND not in DB
    allowed_eftas = catalog_eftas - db_eftas
    print(f"  Need to download (catalog - DB): {len(allowed_eftas)}")

    # Load progress (already uploaded to R2 in previous runs)
    completed = load_progress()
    print(f"  Previously uploaded to R2: {len(completed)}")

    # Remove already-uploaded from allowed
    remaining = allowed_eftas - completed
    print(f"  Still remaining: {len(remaining)}")

    total_stats = {
        "pdfs_uploaded": 0,
        "pdfs_skipped": 0,
        "bytes_uploaded": 0,
        "errors": 0,
    }

    overall_start = time.time()

    for warc_num in range(args.start, args.end + 1):
        warc_filename = WARC_TEMPLATE.format(num=warc_num)
        print(f"\n{'=' * 70}")
        print(f"  WARC {warc_num:05d} of {args.end:05d}")
        print(f"{'=' * 70}")

        # Download WARC
        warc_path = download_warc(warc_filename)
        if warc_path is None:
            print(f"  FAILED to download, skipping")
            continue

        # Extract and upload (only EFTAs in catalog and not in DB)
        stats = extract_and_upload(warc_path, s3_client, completed, allowed_eftas, dry_run=args.dry_run)

        total_stats["pdfs_uploaded"] += stats["pdfs_uploaded"]
        total_stats["pdfs_skipped"] += stats["pdfs_skipped"]
        total_stats["bytes_uploaded"] += stats["bytes_uploaded"]
        total_stats["errors"] += stats["errors"]

        # Delete WARC to free space
        if not args.keep_warc and not args.dry_run:
            print(f"  Deleting {warc_filename} to free disk space...")
            warc_path.unlink()
            print(f"  Deleted.")

    # Final summary
    elapsed = time.time() - overall_start
    print(f"\n{'=' * 70}")
    print(f"  ALL DONE")
    print(f"{'=' * 70}")
    print(f"  Total uploaded:  {total_stats['pdfs_uploaded']}")
    print(f"  Total skipped:   {total_stats['pdfs_skipped']}")
    print(f"  Total data:      {total_stats['bytes_uploaded'] / (1024**3):.2f} GiB")
    print(f"  Total errors:    {total_stats['errors']}")
    print(f"  Total time:      {elapsed / 60:.1f} min")
    if total_stats["pdfs_uploaded"] > 0 and elapsed > 0:
        print(f"  Avg rate:        {total_stats['pdfs_uploaded'] / elapsed * 60:.0f} files/min")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
