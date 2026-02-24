#!/usr/bin/env python3
"""
Multi-Machine Download Worker for PDF Ingestion to R2.

This script coordinates downloading PDFs from multiple sources (GeekenDev mirror,
Azure Blob Storage, DOJ website) and uploading them to Cloudflare R2 storage.

It uses PostgreSQL with FOR UPDATE SKIP LOCKED for atomic batch claiming,
allowing multiple machines to work in parallel without conflicts.

Usage:
    # Run worker for dataset 11
    python download_worker.py --dataset 11 --workers 8

    # Load catalog into queue
    python download_worker.py --load-catalog doj_catalog.txt --dataset 11

    # Sync R2 completion status
    python download_worker.py --sync-r2 --dataset 11

    # Reset failed for retry
    python download_worker.py --retry-failed --dataset 11

    # Show progress
    python download_worker.py --status

    # Migrate from text file progress
    python download_worker.py --migrate-progress r2_upload_progress_ds11.txt --dataset 11
"""

import argparse
import os
import re
import socket
import sys
import threading
import time
import queue as queue_module
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

import boto3
from botocore.config import Config as BotoConfig
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import SessionLocal, engine

# Import source handlers
from sources import (
    SourceRegistry,
    SourceType,
    FileMetadata,
    DownloadResult,
    GeekenZipSource,
    AzureBlobSource,
    DojDirectSource,
)


# ============================================
# CONFIGURATION
# ============================================

# R2 Configuration
R2_ENDPOINT = os.getenv("R2_ENDPOINT", "https://f8370fa3403bc68c2a46a3ad87be970d.r2.cloudflarestorage.com")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET = os.getenv("R2_BUCKET", "epsteinfiles")

# Worker defaults
DEFAULT_BATCH_SIZE = 200
DEFAULT_UPLOAD_WORKERS = 4
DEFAULT_DOWNLOAD_WORKERS = 2
DEFAULT_PREFETCH_QUEUE_SIZE = 50
MAX_RETRIES = 3
STALE_CLAIM_TIMEOUT_MINUTES = 30


# ============================================
# WORKER IDENTITY
# ============================================

@dataclass
class WorkerIdentity:
    """Identifies this worker for debugging/monitoring."""
    machine_name: str
    process_id: int
    worker_thread: int = 0

    @classmethod
    def create(cls, thread_id: int = 0) -> "WorkerIdentity":
        return cls(
            machine_name=socket.gethostname(),
            process_id=os.getpid(),
            worker_thread=thread_id,
        )

    @property
    def worker_id(self) -> str:
        return f"{self.machine_name}:{self.process_id}:{self.worker_thread}"


# ============================================
# WORK QUEUE (DATABASE)
# ============================================

@dataclass
class WorkItem:
    """A single work item from the queue."""
    queue_id: int
    efta_number: str
    source_type: str
    source_path: str
    doj_url: Optional[str]
    r2_key: Optional[str]


class DownloadWorkQueue:
    """
    Database-driven work queue for downloading PDFs.

    Uses PostgreSQL row-level locking to prevent race conditions
    when multiple workers claim work.
    """

    def __init__(self, worker_id: str):
        self.worker_id = worker_id

    def claim_batch(self, dataset_num: int, batch_size: int = DEFAULT_BATCH_SIZE) -> List[WorkItem]:
        """
        Atomically claim a batch of downloads.

        Uses FOR UPDATE SKIP LOCKED to prevent race conditions.
        Returns list of WorkItem that are now claimed by this worker.
        """
        with engine.connect() as conn:
            try:
                result = conn.execute(
                    text("SELECT * FROM claim_download_batch(:dataset, :batch_size, :worker)"),
                    {"dataset": dataset_num, "batch_size": batch_size, "worker": self.worker_id}
                )
                rows = result.fetchall()
                conn.commit()

                return [
                    WorkItem(
                        queue_id=row[0],
                        efta_number=row[1],
                        source_type=row[2],
                        source_path=row[3],
                        doj_url=row[4],
                        r2_key=row[5],
                    )
                    for row in rows
                ]
            except Exception as e:
                logger.error(f"Failed to claim batch: {e}")
                conn.rollback()
                return []

    def mark_completed(self, queue_id: int, r2_key: str, file_size: int, source_used: str):
        """Mark a work item as successfully uploaded."""
        with engine.connect() as conn:
            try:
                conn.execute(
                    text("SELECT complete_download(:qid, :key, :size, :source)"),
                    {"qid": queue_id, "key": r2_key, "size": file_size, "source": source_used}
                )
                conn.commit()
            except Exception as e:
                logger.error(f"Failed to mark completed: {e}")
                conn.rollback()

    def mark_failed(self, queue_id: int, error: str):
        """Mark a work item as failed."""
        with engine.connect() as conn:
            try:
                conn.execute(
                    text("SELECT fail_download(:qid, :error, :max_retries)"),
                    {"qid": queue_id, "error": error[:500], "max_retries": MAX_RETRIES}
                )
                conn.commit()
            except Exception as e:
                logger.error(f"Failed to mark failed: {e}")
                conn.rollback()

    def reclaim_stale(self, timeout_minutes: int = STALE_CLAIM_TIMEOUT_MINUTES) -> int:
        """Reset stale claims back to pending."""
        with engine.connect() as conn:
            try:
                result = conn.execute(
                    text("SELECT reclaim_stale_downloads(:timeout)"),
                    {"timeout": timeout_minutes}
                )
                count = result.scalar() or 0
                conn.commit()
                return count
            except Exception as e:
                logger.error(f"Failed to reclaim stale: {e}")
                conn.rollback()
                return 0

    def get_status(self, dataset_num: Optional[int] = None) -> Dict[str, Any]:
        """Get current queue status."""
        with engine.connect() as conn:
            try:
                if dataset_num:
                    result = conn.execute(
                        text("SELECT * FROM download_progress WHERE dataset_number = :ds"),
                        {"ds": dataset_num}
                    )
                else:
                    result = conn.execute(text("SELECT * FROM download_progress"))

                rows = result.fetchall()
                columns = result.keys()
                return [dict(zip(columns, row)) for row in rows]
            except Exception as e:
                logger.error(f"Failed to get status: {e}")
                return []


# ============================================
# R2 UPLOAD
# ============================================

def create_r2_client():
    """Create a boto3 client for R2."""
    if not R2_ACCESS_KEY or not R2_SECRET_KEY:
        raise ValueError("R2 credentials not configured. Set R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY")

    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        region_name="auto",
        config=BotoConfig(
            retries={"max_attempts": 3, "mode": "adaptive"},
            connect_timeout=30,
            read_timeout=60,
        ),
    )


def upload_to_r2(s3_client, r2_key: str, data: bytes) -> bool:
    """Upload data to R2. Returns True on success."""
    try:
        s3_client.put_object(
            Bucket=R2_BUCKET,
            Key=r2_key,
            Body=data,
            ContentType="application/pdf",
        )
        return True
    except Exception as e:
        logger.error(f"R2 upload failed for {r2_key}: {e}")
        return False


# ============================================
# WORKER STATISTICS
# ============================================

@dataclass
class WorkerStats:
    """Statistics for monitoring."""
    downloaded: int = 0
    uploaded: int = 0
    failed: int = 0
    skipped: int = 0
    bytes_uploaded: int = 0
    start_time: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def increment(self, downloaded: int = 0, uploaded: int = 0, failed: int = 0, bytes_up: int = 0):
        with self.lock:
            self.downloaded += downloaded
            self.uploaded += uploaded
            self.failed += failed
            self.bytes_uploaded += bytes_up

    @property
    def elapsed_minutes(self) -> float:
        return (time.time() - self.start_time) / 60

    @property
    def rate_per_minute(self) -> float:
        elapsed = self.elapsed_minutes
        if elapsed > 0:
            return self.uploaded / elapsed
        return 0.0

    def __str__(self) -> str:
        return (
            f"downloaded={self.downloaded} uploaded={self.uploaded} "
            f"failed={self.failed} rate={self.rate_per_minute:.1f}/min "
            f"data={self.bytes_uploaded / (1024**3):.2f}GB "
            f"elapsed={self.elapsed_minutes:.1f}min"
        )


# ============================================
# UNIFIED DOWNLOAD WORKER
# ============================================

class UnifiedDownloadWorker:
    """
    Unified worker that downloads from multiple sources and uploads to R2.

    Architecture:
    - Download thread(s) claim batches and fetch from sources
    - Prefetch queue buffers downloaded data
    - Upload workers push to R2
    - Database tracks progress for distributed processing
    """

    def __init__(
        self,
        dataset_num: int,
        registry: SourceRegistry,
        upload_workers: int = DEFAULT_UPLOAD_WORKERS,
        download_workers: int = DEFAULT_DOWNLOAD_WORKERS,
        batch_size: int = DEFAULT_BATCH_SIZE,
        prefetch_size: int = DEFAULT_PREFETCH_QUEUE_SIZE,
    ):
        self.dataset_num = dataset_num
        self.registry = registry
        self.upload_workers = upload_workers
        self.download_workers = download_workers
        self.batch_size = batch_size

        self.identity = WorkerIdentity.create()
        self.work_queue = DownloadWorkQueue(self.identity.worker_id)
        self.r2_client = create_r2_client()

        # Internal queues and state
        self._prefetch_queue: queue_module.Queue = queue_module.Queue(maxsize=prefetch_size)
        self._stop_event = threading.Event()

        self.stats = WorkerStats()

    def _download_worker(self, worker_id: int):
        """
        Download worker thread: claims batches and downloads from sources.
        Pushes downloaded data to the prefetch queue for upload workers.
        """
        logger.info(f"Download worker {worker_id} starting")
        local_identity = WorkerIdentity.create(worker_id)
        local_queue = DownloadWorkQueue(local_identity.worker_id)

        while not self._stop_event.is_set():
            try:
                # Periodically reclaim stale items
                if worker_id == 0:  # Only first worker does this
                    reclaimed = local_queue.reclaim_stale()
                    if reclaimed > 0:
                        logger.info(f"Reclaimed {reclaimed} stale items")

                # Claim a batch of work
                work_items = local_queue.claim_batch(self.dataset_num, self.batch_size)

                if not work_items:
                    logger.debug(f"Download worker {worker_id}: no work available, waiting...")
                    time.sleep(5)
                    continue

                logger.info(f"Download worker {worker_id} claimed {len(work_items)} items")

                # Download each item
                for item in work_items:
                    if self._stop_event.is_set():
                        break

                    # Try downloading with fallback
                    result = self.registry.download_with_fallback(
                        efta_number=item.efta_number,
                        source_path=item.source_path,
                        doj_url=item.doj_url,
                    )

                    if result.success:
                        # Build R2 key
                        r2_key = item.r2_key or f"DataSet_{self.dataset_num}/{item.efta_number}.pdf"

                        # Push to upload queue
                        self._prefetch_queue.put((item, result, r2_key))
                        self.stats.increment(downloaded=1)
                    else:
                        # Mark as failed
                        local_queue.mark_failed(item.queue_id, result.error_message or "download_failed")
                        self.stats.increment(failed=1)
                        logger.debug(f"Download failed for {item.efta_number}: {result.error_message}")

            except Exception as e:
                logger.error(f"Download worker {worker_id} error: {e}")
                time.sleep(1)

        # Signal end of downloads
        for _ in range(self.upload_workers):
            self._prefetch_queue.put(None)

        logger.info(f"Download worker {worker_id} stopped")

    def _upload_worker(self, worker_id: int):
        """Upload worker thread: takes from prefetch queue and uploads to R2."""
        logger.info(f"Upload worker {worker_id} starting")
        local_queue = DownloadWorkQueue(self.identity.worker_id)

        while True:
            try:
                job = self._prefetch_queue.get(timeout=5)
            except queue_module.Empty:
                if self._stop_event.is_set():
                    break
                continue

            if job is None:  # Shutdown signal
                break

            item, result, r2_key = job

            try:
                success = upload_to_r2(self.r2_client, r2_key, result.data)

                if success:
                    local_queue.mark_completed(
                        item.queue_id,
                        r2_key,
                        result.file_size,
                        result.source_type.value if result.source_type else "unknown",
                    )
                    self.stats.increment(uploaded=1, bytes_up=result.file_size)
                else:
                    local_queue.mark_failed(item.queue_id, "r2_upload_failed")
                    self.stats.increment(failed=1)

            except Exception as e:
                logger.error(f"Upload worker {worker_id} error: {e}")
                local_queue.mark_failed(item.queue_id, str(e)[:500])
                self.stats.increment(failed=1)
            finally:
                self._prefetch_queue.task_done()

        logger.info(f"Upload worker {worker_id} stopped")

    def run(self):
        """Run the worker until all work is complete or stop is called."""
        logger.info(f"Starting unified download worker for Dataset {self.dataset_num}")
        logger.info(f"Worker ID: {self.identity.worker_id}")
        logger.info(f"Download workers: {self.download_workers}, Upload workers: {self.upload_workers}")

        # Start download workers
        download_threads = []
        for i in range(self.download_workers):
            t = threading.Thread(target=self._download_worker, args=(i,), daemon=True)
            t.start()
            download_threads.append(t)

        # Start upload workers
        upload_threads = []
        for i in range(self.upload_workers):
            t = threading.Thread(target=self._upload_worker, args=(i,), daemon=True)
            t.start()
            upload_threads.append(t)

        # Monitor progress
        try:
            last_report = time.time()
            empty_cycles = 0

            while not self._stop_event.is_set():
                time.sleep(5)

                # Check if all download workers are done
                all_download_done = all(not t.is_alive() for t in download_threads)
                queue_empty = self._prefetch_queue.empty()

                if all_download_done and queue_empty:
                    empty_cycles += 1
                    if empty_cycles >= 3:  # Wait a bit to ensure uploads finish
                        logger.info("All work complete")
                        break
                else:
                    empty_cycles = 0

                # Progress report
                if time.time() - last_report >= 30:
                    logger.info(f"Progress: {self.stats}")
                    last_report = time.time()

        except KeyboardInterrupt:
            logger.info("Interrupted, shutting down...")
        finally:
            self._stop_event.set()

            # Wait for threads to finish
            for t in download_threads:
                t.join(timeout=10)
            for t in upload_threads:
                t.join(timeout=10)

        logger.info(f"Final stats: {self.stats}")

    def stop(self):
        """Signal the worker to stop."""
        self._stop_event.set()


# ============================================
# CATALOG LOADING
# ============================================

def load_catalog_to_queue(catalog_file: str, dataset_num: int, source_type: str = "geeken_zip"):
    """
    Load EFTA list into download_queue with DOJ URLs for fallback.

    Supports two formats:
    1. Tab-separated: EFTA\\tDATASET\\tURL (doj_catalog.txt)
    2. Simple list: one EFTA per line
    """
    entries = []
    path = Path(catalog_file)

    if not path.exists():
        logger.error(f"Catalog file not found: {catalog_file}")
        return 0

    logger.info(f"Loading catalog from {catalog_file}...")

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            parts = line.split("\t")

            if len(parts) >= 3:
                # Tab-separated format: EFTA\tDATASET\tURL
                efta, ds, doj_url = parts[0], parts[1], parts[2]
                if ds != str(dataset_num):
                    continue
            elif len(parts) == 1:
                # Simple EFTA list
                efta = parts[0]
                doj_url = None
            else:
                continue

            # Validate EFTA format
            if not re.match(r"EFTA\d{8,11}$", efta, re.IGNORECASE):
                continue

            entries.append({
                "efta_number": efta.upper(),
                "dataset_number": dataset_num,
                "source_type": source_type,
                "source_path": efta.upper(),  # Will be resolved by source handler
                "doj_url": doj_url,
                "r2_key": f"DataSet_{dataset_num}/{efta.upper()}.pdf",
            })

    if not entries:
        logger.warning("No entries found in catalog")
        return 0

    logger.info(f"Inserting {len(entries)} entries into download_queue...")

    # Batch insert
    with engine.connect() as conn:
        try:
            # Insert in chunks
            chunk_size = 1000
            inserted = 0

            for i in range(0, len(entries), chunk_size):
                chunk = entries[i:i + chunk_size]
                conn.execute(
                    text("""
                        INSERT INTO download_queue
                            (efta_number, dataset_number, source_type, source_path, doj_url, r2_key)
                        VALUES
                            (:efta_number, :dataset_number, :source_type, :source_path, :doj_url, :r2_key)
                        ON CONFLICT (efta_number) DO NOTHING
                    """),
                    chunk,
                )
                inserted += len(chunk)
                logger.info(f"Inserted {inserted}/{len(entries)}...")

            conn.commit()
            logger.info(f"Loaded {len(entries)} entries into queue")
            return len(entries)

        except Exception as e:
            logger.error(f"Failed to load catalog: {e}")
            conn.rollback()
            return 0


def sync_r2_completion(dataset_num: int):
    """Mark queue items as completed if they already exist in R2."""
    logger.info(f"Syncing R2 completion status for Dataset {dataset_num}...")

    try:
        s3_client = create_r2_client()
        prefix = f"DataSet_{dataset_num}/"
        existing = set()

        paginator = s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=R2_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                match = re.search(r"(EFTA\d+)\.pdf$", obj["Key"], re.IGNORECASE)
                if match:
                    existing.add(match.group(1).upper())

        logger.info(f"Found {len(existing)} existing files in R2")

        if existing:
            with engine.connect() as conn:
                # Update in chunks
                efta_list = list(existing)
                chunk_size = 1000
                updated = 0

                for i in range(0, len(efta_list), chunk_size):
                    chunk = efta_list[i:i + chunk_size]
                    result = conn.execute(
                        text("""
                            UPDATE download_queue
                            SET status = 'completed',
                                completed_at = NOW(),
                                actual_source_used = 'pre_existing'
                            WHERE efta_number = ANY(:eftas)
                              AND status IN ('pending', 'failed')
                        """),
                        {"eftas": chunk},
                    )
                    updated += result.rowcount

                conn.commit()
                logger.info(f"Marked {updated} items as completed")

        return len(existing)

    except Exception as e:
        logger.error(f"Failed to sync R2: {e}")
        return 0


def migrate_text_progress(progress_file: str, dataset_num: int):
    """Import existing r2_upload_progress_ds*.txt as completed."""
    path = Path(progress_file)

    if not path.exists():
        logger.error(f"Progress file not found: {progress_file}")
        return 0

    logger.info(f"Migrating progress from {progress_file}...")

    completed = []
    with open(path, "r") as f:
        for line in f:
            efta = line.strip()
            if efta and re.match(r"EFTA\d+$", efta, re.IGNORECASE):
                completed.append(efta.upper())

    if not completed:
        logger.warning("No completed EFTAs found in progress file")
        return 0

    logger.info(f"Found {len(completed)} completed EFTAs")

    with engine.connect() as conn:
        try:
            # Update in chunks
            chunk_size = 1000
            updated = 0

            for i in range(0, len(completed), chunk_size):
                chunk = completed[i:i + chunk_size]
                result = conn.execute(
                    text("""
                        UPDATE download_queue
                        SET status = 'completed',
                            completed_at = NOW(),
                            actual_source_used = 'migrated'
                        WHERE efta_number = ANY(:eftas)
                          AND dataset_number = :ds
                    """),
                    {"eftas": chunk, "ds": dataset_num},
                )
                updated += result.rowcount

            conn.commit()
            logger.info(f"Migrated {updated} items as completed")
            return updated

        except Exception as e:
            logger.error(f"Failed to migrate progress: {e}")
            conn.rollback()
            return 0


def reset_failed_for_retry(dataset_num: int):
    """Reset failed downloads to pending for retry."""
    with engine.connect() as conn:
        try:
            result = conn.execute(
                text("SELECT reset_failed_for_retry(:ds, :max_retries)"),
                {"ds": dataset_num, "max_retries": MAX_RETRIES},
            )
            count = result.scalar() or 0
            conn.commit()
            logger.info(f"Reset {count} failed items for retry")
            return count
        except Exception as e:
            logger.error(f"Failed to reset failed items: {e}")
            conn.rollback()
            return 0


def show_status(dataset_num: Optional[int] = None):
    """Show current download progress."""
    queue = DownloadWorkQueue("status-check")
    statuses = queue.get_status(dataset_num)

    if not statuses:
        print("No download queue data found.")
        return

    print("\n=== Download Progress ===\n")
    print(f"{'Dataset':<10} {'Pending':<10} {'In Progress':<12} {'Completed':<12} {'Failed':<10} {'Skipped':<10} {'Total':<10} {'%':<8} {'GB':<10}")
    print("-" * 100)

    for row in statuses:
        print(
            f"{row.get('dataset_number', 'N/A'):<10} "
            f"{row.get('pending', 0):<10} "
            f"{row.get('in_progress', 0):<12} "
            f"{row.get('completed', 0):<12} "
            f"{row.get('failed', 0):<10} "
            f"{row.get('skipped', 0):<10} "
            f"{row.get('total', 0):<10} "
            f"{row.get('pct_complete', 0):<8.1f} "
            f"{row.get('gb_transferred', 0):<10.2f}"
        )

    print()


# ============================================
# MAIN
# ============================================

def main():
    parser = argparse.ArgumentParser(
        description="Multi-machine download worker for PDF ingestion to R2"
    )

    # Required for most operations
    parser.add_argument("--dataset", type=int, help="Dataset number (e.g., 9 or 11)")

    # Worker configuration
    parser.add_argument("--workers", type=int, default=DEFAULT_UPLOAD_WORKERS,
                        help="Number of upload workers")
    parser.add_argument("--download-workers", type=int, default=DEFAULT_DOWNLOAD_WORKERS,
                        help="Number of download workers")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                        help="Batch size for claiming")

    # Source selection
    parser.add_argument("--source", choices=["geeken", "azure", "doj", "auto"], default="auto",
                        help="Preferred source (auto uses all with fallback)")

    # Management commands
    parser.add_argument("--load-catalog", metavar="FILE",
                        help="Load catalog file into download queue")
    parser.add_argument("--sync-r2", action="store_true",
                        help="Sync completion status from R2")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Reset failed items for retry")
    parser.add_argument("--migrate-progress", metavar="FILE",
                        help="Migrate from text progress file")
    parser.add_argument("--status", action="store_true",
                        help="Show download progress")

    args = parser.parse_args()

    # Handle status command (no dataset required)
    if args.status:
        show_status(args.dataset)
        return 0

    # All other commands require dataset
    if not args.dataset and not args.status:
        parser.error("--dataset is required for this operation")

    # Handle management commands
    if args.load_catalog:
        source_type = "geeken_zip" if args.source in ("geeken", "auto") else args.source
        count = load_catalog_to_queue(args.load_catalog, args.dataset, source_type)
        print(f"Loaded {count} entries into queue")
        return 0

    if args.sync_r2:
        count = sync_r2_completion(args.dataset)
        print(f"Synced {count} existing R2 files")
        return 0

    if args.retry_failed:
        count = reset_failed_for_retry(args.dataset)
        print(f"Reset {count} failed items for retry")
        return 0

    if args.migrate_progress:
        count = migrate_text_progress(args.migrate_progress, args.dataset)
        print(f"Migrated {count} items from progress file")
        return 0

    # Run worker
    logger.info(f"Starting download worker for Dataset {args.dataset}")

    # Set up source registry
    registry = SourceRegistry()

    if args.source in ("geeken", "auto"):
        try:
            geeken = GeekenZipSource(args.dataset)
            registry.register(geeken, priority=1 if args.source == "geeken" else 1)
            logger.info("Registered GeekenDev source")
        except Exception as e:
            logger.warning(f"GeekenDev source unavailable: {e}")

    if args.source in ("azure", "auto"):
        try:
            azure = AzureBlobSource(args.dataset)
            registry.register(azure, priority=1 if args.source == "azure" else 2)
            logger.info("Registered Azure source")
        except Exception as e:
            logger.warning(f"Azure source unavailable: {e}")

    if args.source in ("doj", "auto"):
        try:
            doj = DojDirectSource()
            registry.register(doj, priority=1 if args.source == "doj" else 3)
            logger.info("Registered DOJ direct source (last resort)")
        except Exception as e:
            logger.warning(f"DOJ source unavailable: {e}")

    # Check availability
    available = registry.get_available_sources()
    if not available:
        logger.error("No sources available! Check credentials and network.")
        return 1

    logger.info(f"Available sources: {[s.source_type.value for s in available]}")

    # Create and run worker
    worker = UnifiedDownloadWorker(
        dataset_num=args.dataset,
        registry=registry,
        upload_workers=args.workers,
        download_workers=args.download_workers,
        batch_size=args.batch_size,
    )

    try:
        worker.run()
    except KeyboardInterrupt:
        logger.info("Interrupted")
        worker.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
