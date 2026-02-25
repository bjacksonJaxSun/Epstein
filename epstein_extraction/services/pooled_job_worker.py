"""
Pooled Job Worker - Claims and executes jobs from the job_pool table.

This worker implements a multi-machine job pool using PostgreSQL's FOR UPDATE SKIP LOCKED
for atomic batch claiming. Multiple workers can run on different machines, and they will
safely compete for jobs without duplicates.

Features:
- Atomic batch claiming with FOR UPDATE SKIP LOCKED
- Multiple concurrent jobs per worker
- Pluggable job type handlers
- Automatic stale job recovery
- Database-based code distribution (server publishes, clients pull)
- Graceful shutdown

Usage:
    python pooled_job_worker.py --server --job-types general   # Server: publish code + run
    python pooled_job_worker.py --job-types general            # Client: pull code + run
    python pooled_job_worker.py --no-update                    # Skip version check

Environment Variables:
    DATABASE_URL: PostgreSQL connection string (default: from .env or hardcoded)
"""

import os
import sys
import socket
import signal
import asyncio
import argparse
import hashlib
import shutil
from dataclasses import dataclass
from typing import Callable, Optional
import json
import logging
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.job_handlers import handle_general_job, JobResult

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class WorkerIdentity:
    """Identifies a worker instance across machines."""
    machine_name: str
    process_id: int
    worker_thread: int = 0

    @property
    def worker_id(self) -> str:
        return f"{self.machine_name}:{self.process_id}:{self.worker_thread}"


class DatabaseUpdater:
    """
    Handles code distribution via PostgreSQL.

    Server mode: reads managed files from disk and publishes to the worker_code table.
    Client mode: checks the DB for newer versions and pulls/writes files, then restarts.
    """

    # Files managed by the updater, relative to base_dir (epstein_extraction/)
    MANAGED_FILES = [
        'services/pooled_job_worker.py',
        'services/job_handlers/__init__.py',
        'services/job_handlers/general_handler.py',
    ]

    def __init__(self, db_url: str, base_dir: Optional[Path] = None):
        self.db_url = db_url
        # base_dir = the epstein_extraction/ directory
        self.base_dir = base_dir or Path(__file__).resolve().parent.parent

    def _get_connection(self):
        return psycopg2.connect(self.db_url)

    # ------------------------------------------------------------------
    # Hashing
    # ------------------------------------------------------------------

    def _file_hash(self, content: str) -> str:
        """SHA256 of a single file's content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def compute_local_hash(self) -> str:
        """
        Combined hash of all managed files.
        SHA256 of sorted (relative_path + individual_hash) pairs.
        """
        parts = []
        for rel in sorted(self.MANAGED_FILES):
            fpath = self.base_dir / rel
            if fpath.exists():
                content = fpath.read_text(encoding='utf-8')
                parts.append(f"{rel}:{self._file_hash(content)}")
            else:
                parts.append(f"{rel}:MISSING")
        combined = '\n'.join(parts)
        return hashlib.sha256(combined.encode('utf-8')).hexdigest()

    def read_managed_files(self) -> dict[str, str]:
        """Read all managed files into a dict of {relative_path: contents}."""
        files = {}
        for rel in self.MANAGED_FILES:
            fpath = self.base_dir / rel
            if fpath.exists():
                files[rel] = fpath.read_text(encoding='utf-8')
            else:
                logger.warning(f"Managed file not found: {fpath}")
        return files

    # ------------------------------------------------------------------
    # Server (publisher)
    # ------------------------------------------------------------------

    def publish(self) -> tuple[bool, str]:
        """
        Publish current managed files to the database.

        Returns:
            (was_new, version_hash) — was_new is True if a new row was inserted.
        """
        version_hash = self.compute_local_hash()
        files = self.read_managed_files()

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT publish_worker_code(%s, %s, %s, %s)",
                        (version_hash, json.dumps(files), socket.gethostname(), None)
                    )
                    was_new = cur.fetchone()[0]
                    conn.commit()
            if was_new:
                logger.info(f"Published version {version_hash[:16]} with {len(files)} files")
            else:
                logger.info(f"Version {version_hash[:16]} already published — no change")
            return was_new, version_hash
        except Exception as e:
            logger.error(f"Failed to publish code: {e}")
            raise

    # ------------------------------------------------------------------
    # Client (puller)
    # ------------------------------------------------------------------

    def get_remote_version(self) -> Optional[str]:
        """Get the latest version hash from the database."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT get_latest_worker_version()")
                    row = cur.fetchone()
                    return row[0] if row else None
        except Exception as e:
            logger.error(f"Failed to get remote version: {e}")
            return None

    def needs_update(self) -> tuple[bool, str, Optional[str]]:
        """
        Check whether the local files are behind the database version.

        Returns:
            (update_needed, local_hash, remote_hash)
        """
        local_hash = self.compute_local_hash()
        remote_hash = self.get_remote_version()
        if remote_hash is None:
            # No code published yet — nothing to update from
            return False, local_hash, remote_hash
        return local_hash != remote_hash, local_hash, remote_hash

    def pull_and_apply(self, version_hash: str) -> bool:
        """
        Fetch code from DB and overwrite local files, backing up originals.

        Returns True on success.
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT get_worker_code(%s)", (version_hash,))
                    row = cur.fetchone()
                    if not row or row[0] is None:
                        logger.error(f"No code found for version {version_hash[:16]}")
                        return False
                    files = row[0]
                    # psycopg2 may return a string or a dict depending on version
                    if isinstance(files, str):
                        files = json.loads(files)
        except Exception as e:
            logger.error(f"Failed to fetch code from DB: {e}")
            return False

        # Write each file, backing up the original
        for rel_path, content in files.items():
            target = self.base_dir / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)

            if target.exists():
                backup = target.with_suffix(target.suffix + '.bak')
                shutil.copy2(target, backup)
                logger.info(f"Backed up {rel_path} -> {backup.name}")

            target.write_text(content, encoding='utf-8')
            logger.info(f"Updated {rel_path}")

        logger.info(f"Applied version {version_hash[:16]} ({len(files)} files)")
        return True

    def restart_worker(self):
        """Restart the current process with the same arguments."""
        logger.info("Restarting worker with updated code...")
        python = sys.executable
        os.execv(python, [python] + sys.argv)

    def check_and_apply(self) -> bool:
        """
        Full client cycle: check version, pull if behind, restart.

        Returns True if the worker should continue (no update needed).
        If an update is applied, this method does not return (os.execv).
        """
        update_needed, local_hash, remote_hash = self.needs_update()
        logger.info(f"Local version: {local_hash[:16]}")

        if not update_needed:
            if remote_hash:
                logger.info("Worker code is up to date")
            else:
                logger.info("No published code in DB — running local version")
            return True

        logger.info(f"Update available: {local_hash[:16]} -> {remote_hash[:16]}")
        if self.pull_and_apply(remote_hash):
            self.restart_worker()
            # Won't reach here
        else:
            logger.warning("Failed to apply update — continuing with current version")
        return True


@dataclass
class MachineCapabilities:
    """Detected machine capabilities for optimizing worker performance."""
    cpu_count: int
    cpu_count_physical: int
    memory_total_gb: float
    memory_available_gb: float
    hostname: str

    @classmethod
    def detect(cls) -> 'MachineCapabilities':
        """Detect the current machine's capabilities."""
        import multiprocessing

        cpu_count = os.cpu_count() or 1
        cpu_count_physical = cpu_count

        # Try to get physical core count (without hyperthreading)
        try:
            import psutil
            cpu_count_physical = psutil.cpu_count(logical=False) or cpu_count
            memory_info = psutil.virtual_memory()
            memory_total_gb = memory_info.total / (1024**3)
            memory_available_gb = memory_info.available / (1024**3)
        except ImportError:
            # psutil not available, use defaults
            memory_total_gb = 8.0  # Assume 8GB
            memory_available_gb = 4.0  # Assume 4GB available

        return cls(
            cpu_count=cpu_count,
            cpu_count_physical=cpu_count_physical,
            memory_total_gb=memory_total_gb,
            memory_available_gb=memory_available_gb,
            hostname=socket.gethostname()
        )

    def recommend_concurrent_jobs(self, job_type: str = 'general') -> int:
        """
        Recommend number of concurrent jobs based on machine capabilities.

        Args:
            job_type: Type of jobs being processed (affects resource estimation)

        Returns:
            Recommended number of concurrent jobs
        """
        # Base recommendation on physical cores
        # Leave 1 core for system + main worker process
        base = max(1, self.cpu_count_physical - 1)

        # Adjust based on available memory
        # Assume each job needs ~500MB for general tasks
        memory_jobs = {
            'general': 0.5,    # 500MB per job
            'ocr': 1.0,        # 1GB per job (OCR is memory-intensive)
            'vision': 2.0,     # 2GB per job (vision models are heavy)
            'entity': 0.3,     # 300MB per job
        }

        mem_per_job = memory_jobs.get(job_type, 0.5)
        memory_based = int(self.memory_available_gb / mem_per_job)

        # Take the minimum of CPU-based and memory-based recommendations
        recommended = min(base, memory_based)

        # Ensure at least 1, cap at 16 (avoid overwhelming the system)
        return max(1, min(recommended, 16))

    def __str__(self) -> str:
        return (
            f"Machine: {self.hostname}\n"
            f"  CPUs: {self.cpu_count} logical, {self.cpu_count_physical} physical\n"
            f"  Memory: {self.memory_total_gb:.1f}GB total, {self.memory_available_gb:.1f}GB available"
        )


def check_and_update(db_url: str, is_server: bool, skip_update: bool = False) -> bool:
    """
    Publish or pull code depending on mode.

    Args:
        db_url: PostgreSQL connection string
        is_server: True = publish local code to DB, False = pull from DB
        skip_update: If True, skip all version checking

    Returns:
        True if worker should continue (always, unless os.execv replaces the process)
    """
    if skip_update:
        logger.info("Skipping version check (--no-update)")
        return True

    try:
        updater = DatabaseUpdater(db_url)

        if is_server:
            updater.publish()
        else:
            updater.check_and_apply()

        return True
    except Exception as e:
        logger.warning(f"Code distribution check failed: {e}")
        logger.info("Continuing with current version...")
        return True


class PooledJobWorker:
    """
    Worker that claims and executes jobs from the job_pool table.

    Supports:
    - Atomic batch claiming with FOR UPDATE SKIP LOCKED
    - Multiple concurrent jobs per worker
    - Pluggable job type handlers
    - Automatic stale job recovery
    - Graceful shutdown
    """

    def __init__(
        self,
        db_url: str,
        job_types: Optional[list[str]] = None,
        max_concurrent: int = 3,
        batch_size: int = 5,
        poll_interval: float = 2.0,
        stale_timeout_minutes: int = 30,
        updater: Optional['DatabaseUpdater'] = None
    ):
        """
        Initialize the worker.

        Args:
            db_url: PostgreSQL connection string
            job_types: List of job types to process (None = all types)
            max_concurrent: Maximum concurrent jobs to run
            batch_size: Number of jobs to claim per batch
            poll_interval: Seconds between polling for new jobs
            stale_timeout_minutes: Minutes before a claimed job is considered stale
            updater: DatabaseUpdater for periodic version checks (client mode only)
        """
        self.db_url = db_url
        self.identity = WorkerIdentity(socket.gethostname(), os.getpid())
        self.job_types = job_types
        self.max_concurrent = max_concurrent
        self.batch_size = batch_size
        self.poll_interval = poll_interval
        self.stale_timeout_minutes = stale_timeout_minutes
        self.handlers: dict[str, Callable[[dict], JobResult]] = {}
        self.shutdown_requested = False
        self.active_jobs = 0
        self.updater = updater

        # Register default handlers
        self.register_handler('general', handle_general_job)

    def register_handler(self, job_type: str, handler: Callable[[dict], JobResult]):
        """Register a handler function for a job type."""
        self.handlers[job_type] = handler
        logger.info(f"Registered handler for job type: {job_type}")

    def _get_connection(self):
        """Get a new database connection."""
        return psycopg2.connect(self.db_url)

    def claim_batch(self) -> list[dict]:
        """Claim a batch of jobs atomically."""
        slots_available = self.max_concurrent - self.active_jobs
        if slots_available <= 0:
            return []

        batch_size = min(self.batch_size, slots_available)

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Convert job_types list to PostgreSQL array or NULL
                    job_types_param = self.job_types if self.job_types else None

                    cur.execute(
                        "SELECT * FROM claim_job_batch(%s, %s, %s)",
                        (self.identity.worker_id, job_types_param, batch_size)
                    )
                    jobs = cur.fetchall()
                    conn.commit()

                    if jobs:
                        logger.info(f"Claimed {len(jobs)} jobs")

                    return [dict(j) for j in jobs]
        except Exception as e:
            logger.error(f"Failed to claim jobs: {e}")
            return []

    def start_job(self, job_id: int):
        """Mark job as running."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT start_job(%s)", (job_id,))
                    conn.commit()
        except Exception as e:
            logger.error(f"Failed to start job {job_id}: {e}")

    def complete_job(self, job_id: int, result: JobResult):
        """Mark job as completed."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    result_json = json.dumps(result.result_data) if result.result_data else None
                    cur.execute(
                        "SELECT complete_job(%s, %s, %s, %s)",
                        (job_id, result_json, result.output, result.exit_code)
                    )
                    conn.commit()
        except Exception as e:
            logger.error(f"Failed to complete job {job_id}: {e}")

    def fail_job(self, job_id: int, error: str, output: str = "", exit_code: int = -1):
        """Mark job as failed."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT fail_job(%s, %s, %s, %s)",
                        (job_id, error, output, exit_code)
                    )
                    conn.commit()
        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as failed: {e}")

    def reclaim_stale(self):
        """Reclaim stale jobs from crashed workers."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT reclaim_stale_jobs(%s)", (self.stale_timeout_minutes,))
                    count = cur.fetchone()[0]
                    conn.commit()
                    if count > 0:
                        logger.info(f"Reclaimed {count} stale jobs")
        except Exception as e:
            logger.error(f"Failed to reclaim stale jobs: {e}")

    async def process_job(self, job: dict):
        """Process a single job."""
        job_id = job['job_id']
        job_type = job['job_type']
        payload = job['payload']

        self.active_jobs += 1
        try:
            self.start_job(job_id)
            logger.info(f"Processing job {job_id} ({job_type})")

            # Find handler
            handler = self.handlers.get(job_type)
            if not handler:
                handler = self.handlers.get('general')
            if not handler:
                raise ValueError(f"No handler for job type: {job_type}")

            # Execute handler in thread pool to not block event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, handler, payload)

            if result.success:
                self.complete_job(job_id, result)
                logger.info(f"Job {job_id} completed successfully (exit_code={result.exit_code})")
            else:
                self.fail_job(job_id, result.error or "Unknown error", result.output, result.exit_code)
                logger.warning(f"Job {job_id} failed: {result.error}")

        except Exception as e:
            self.fail_job(job_id, str(e))
            logger.exception(f"Job {job_id} exception: {e}")
        finally:
            self.active_jobs -= 1

    async def run(self):
        """Main worker loop."""
        logger.info(f"Worker {self.identity.worker_id} starting")
        logger.info(f"Job types: {self.job_types or 'all'}")
        logger.info(f"Max concurrent: {self.max_concurrent}")
        logger.info(f"Batch size: {self.batch_size}")
        logger.info(f"Poll interval: {self.poll_interval}s")
        logger.info(f"Stale timeout: {self.stale_timeout_minutes}min")

        stale_check_counter = 0
        # Check for code updates every ~15 seconds (at 2s poll interval ≈ 7-8 loops)
        update_check_interval = max(1, int(15 / self.poll_interval))
        update_check_counter = 0
        pending_update_hash: Optional[str] = None

        while not self.shutdown_requested:
            # Periodic stale check (every ~60 seconds at 2s poll interval)
            stale_check_counter += 1
            if stale_check_counter >= 30:
                self.reclaim_stale()
                stale_check_counter = 0

            # Periodic code version check (client mode only)
            if self.updater:
                update_check_counter += 1
                if update_check_counter >= update_check_interval:
                    update_check_counter = 0
                    try:
                        needed, _, remote_hash = self.updater.needs_update()
                        if needed and remote_hash:
                            pending_update_hash = remote_hash
                            logger.info(f"Code update available: {remote_hash[:16]}")
                    except Exception as e:
                        logger.debug(f"Version check failed: {e}")

            # If an update is pending and no jobs are active, apply it now
            if pending_update_hash and self.active_jobs == 0:
                logger.info("No active jobs — applying code update and restarting")
                if self.updater.pull_and_apply(pending_update_hash):
                    self.updater.restart_worker()
                else:
                    logger.warning("Failed to apply update — will retry next cycle")
                    pending_update_hash = None

            # Claim and process jobs
            jobs = self.claim_batch()
            if jobs:
                # Process all claimed jobs concurrently
                await asyncio.gather(*[self.process_job(j) for j in jobs])
            else:
                # No jobs available, wait before polling again
                await asyncio.sleep(self.poll_interval)

        logger.info("Worker shutting down")

    def shutdown(self):
        """Request graceful shutdown."""
        logger.info("Shutdown requested")
        self.shutdown_requested = True


def main():
    parser = argparse.ArgumentParser(
        description='Pooled Job Worker - Multi-machine job distribution',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Server mode: publish code to DB and start worker
  python pooled_job_worker.py --server --job-types general

  # Client mode: pull code from DB and start worker
  python pooled_job_worker.py --job-types general

  # Process specific job types with custom concurrency
  python pooled_job_worker.py --job-types ocr,entity --max-concurrent 5

  # Show machine capabilities and recommended settings
  python pooled_job_worker.py --show-capabilities

  # Skip all version checking
  python pooled_job_worker.py --no-update --job-types general
"""
    )
    parser.add_argument('--job-types', type=str, help='Comma-separated list of job types to process')
    parser.add_argument('--max-concurrent', type=int, default=None,
                        help='Maximum concurrent jobs (auto-detected if not specified)')
    parser.add_argument('--batch-size', type=int, default=5, help='Batch size for claiming jobs')
    parser.add_argument('--poll-interval', type=float, default=2.0, help='Poll interval in seconds')
    parser.add_argument('--stale-timeout', type=int, default=30, help='Stale job timeout in minutes')
    parser.add_argument('--db-url', type=str, help='Database URL (or set DATABASE_URL env var)')
    parser.add_argument('--server', action='store_true',
                        help='Server mode: publish local code to DB on startup')
    parser.add_argument('--no-update', action='store_true', help='Skip all version checking')
    parser.add_argument('--show-capabilities', action='store_true',
                        help='Show machine capabilities and recommended settings')
    args = parser.parse_args()

    # Detect machine capabilities
    capabilities = MachineCapabilities.detect()

    # Handle show-capabilities mode
    if args.show_capabilities:
        print("\n=== Machine Capabilities ===")
        print(capabilities)
        print("\n=== Recommended Concurrent Jobs ===")
        for job_type in ['general', 'ocr', 'vision', 'entity']:
            recommended = capabilities.recommend_concurrent_jobs(job_type)
            print(f"  {job_type}: {recommended} concurrent jobs")
        sys.exit(0)

    # Get database URL (needed before update check)
    db_url = args.db_url or os.environ.get('DATABASE_URL')
    if not db_url:
        # Default for Epstein project - BobbyHomeEP via Tailscale
        db_url = "host=100.75.137.22 dbname=epstein_documents user=epstein_user password=epstein_secure_pw_2024"

    # Publish or pull code on startup (unless --no-update)
    check_and_update(db_url, is_server=args.server, skip_update=args.no_update)

    # Parse job types
    job_types = None
    if args.job_types:
        job_types = [t.strip() for t in args.job_types.split(',')]

    # Auto-detect max_concurrent if not specified
    max_concurrent = args.max_concurrent
    if max_concurrent is None:
        # Use the first job type for memory estimation, or 'general' as default
        primary_job_type = job_types[0] if job_types else 'general'
        max_concurrent = capabilities.recommend_concurrent_jobs(primary_job_type)
        logger.info(f"Auto-detected max_concurrent={max_concurrent} for {primary_job_type} jobs")

    # Log machine capabilities
    logger.info(f"Machine: {capabilities.hostname}")
    logger.info(f"CPUs: {capabilities.cpu_count} logical, {capabilities.cpu_count_physical} physical")
    logger.info(f"Memory: {capabilities.memory_total_gb:.1f}GB total, {capabilities.memory_available_gb:.1f}GB available")

    # Set up periodic updater for client mode
    updater = None
    if not args.server and not args.no_update:
        updater = DatabaseUpdater(db_url)

    # Create worker
    worker = PooledJobWorker(
        db_url=db_url,
        job_types=job_types,
        max_concurrent=max_concurrent,
        batch_size=args.batch_size,
        poll_interval=args.poll_interval,
        stale_timeout_minutes=args.stale_timeout,
        updater=updater
    )

    # Handle signals for graceful shutdown
    def signal_handler(sig, frame):
        worker.shutdown()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run worker
    asyncio.run(worker.run())


if __name__ == '__main__':
    main()
