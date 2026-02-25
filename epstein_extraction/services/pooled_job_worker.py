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
- Auto-update from git repository
- Graceful shutdown

Usage:
    python pooled_job_worker.py [--job-types general,ocr] [--max-concurrent 3]
    python pooled_job_worker.py --check-update   # Check and update if needed
    python pooled_job_worker.py --no-update      # Skip version check

Environment Variables:
    DATABASE_URL: PostgreSQL connection string (default: from .env or hardcoded)
"""

import os
import sys
import socket
import signal
import asyncio
import argparse
import subprocess
import hashlib
import shutil
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional, Any
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


class AutoUpdater:
    """
    Handles automatic updates of the worker service from git repository.
    """

    def __init__(self, repo_path: Optional[Path] = None):
        """
        Initialize the auto-updater.

        Args:
            repo_path: Path to the git repository root. Auto-detected if None.
        """
        self.repo_path = repo_path or self._find_repo_root()
        self.worker_script = Path(__file__).resolve()

    def _find_repo_root(self) -> Path:
        """Find the git repository root by walking up the directory tree."""
        current = Path(__file__).resolve().parent
        while current != current.parent:
            if (current / '.git').exists():
                return current
            current = current.parent
        raise RuntimeError("Could not find git repository root")

    def get_local_hash(self) -> str:
        """Get SHA256 hash of the local worker script (first 16 chars)."""
        content = self.worker_script.read_bytes()
        return hashlib.sha256(content).hexdigest()[:16]

    def get_repo_hash(self) -> str:
        """Get SHA256 hash of the worker script in the repo (first 16 chars)."""
        # The canonical location in the repo
        repo_script = self.repo_path / 'epstein_extraction' / 'services' / 'pooled_job_worker.py'
        if repo_script.exists():
            content = repo_script.read_bytes()
            return hashlib.sha256(content).hexdigest()[:16]
        return self.get_local_hash()

    def git_pull(self) -> tuple[bool, str]:
        """
        Pull latest changes from the remote repository.

        Returns:
            Tuple of (success, output_message)
        """
        try:
            result = subprocess.run(
                ['git', 'pull', '--ff-only'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "Git pull timed out"
        except Exception as e:
            return False, str(e)

    def check_for_updates(self) -> tuple[bool, str, str]:
        """
        Check if updates are available.

        Returns:
            Tuple of (update_available, local_hash, remote_hash)
        """
        # First, fetch to see what's available
        try:
            subprocess.run(
                ['git', 'fetch', '--quiet'],
                cwd=self.repo_path,
                capture_output=True,
                timeout=30
            )
        except Exception:
            pass  # Continue even if fetch fails

        # Check if we're behind
        try:
            result = subprocess.run(
                ['git', 'status', '-uno'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            behind = 'behind' in result.stdout.lower()
        except Exception:
            behind = False

        local_hash = self.get_local_hash()
        repo_hash = self.get_repo_hash()

        return behind or (local_hash != repo_hash), local_hash, repo_hash

    def update_and_restart(self) -> bool:
        """
        Pull updates and restart the worker.

        Returns:
            True if update was successful (worker will restart)
        """
        logger.info("Checking for updates...")

        # Check current state
        update_available, local_hash, _ = self.check_for_updates()

        if not update_available:
            logger.info(f"Worker is up to date (hash: {local_hash})")
            return False

        logger.info("Update available, pulling latest changes...")

        # Backup current script
        backup_path = self.worker_script.with_suffix('.py.bak')
        shutil.copy2(self.worker_script, backup_path)
        logger.info(f"Backed up current script to {backup_path}")

        # Pull updates
        success, message = self.git_pull()
        if not success:
            logger.error(f"Failed to pull updates: {message}")
            # Restore backup
            shutil.copy2(backup_path, self.worker_script)
            return False

        logger.info(f"Git pull: {message}")

        # Verify the new script
        new_hash = self.get_local_hash()
        logger.info(f"Updated from {local_hash} to {new_hash}")

        # Restart the worker
        logger.info("Restarting worker with updated code...")
        python = sys.executable
        os.execv(python, [python] + sys.argv)

        # Won't reach here
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


def check_and_update(skip_update: bool = False) -> bool:
    """
    Check for updates and apply them if available.

    Args:
        skip_update: If True, skip the update check

    Returns:
        True if worker should continue, False if it restarted
    """
    if skip_update:
        logger.info("Skipping version check (--no-update)")
        return True

    try:
        updater = AutoUpdater()
        update_available, local_hash, repo_hash = updater.check_for_updates()

        logger.info(f"Local version: {local_hash}")

        if update_available:
            logger.info(f"Update available (repo: {repo_hash})")
            updater.update_and_restart()
            # Won't reach here if restart succeeded
            return False
        else:
            logger.info("Worker is up to date")
            return True

    except Exception as e:
        logger.warning(f"Auto-update check failed: {e}")
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
        stale_timeout_minutes: int = 30
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

        while not self.shutdown_requested:
            # Periodic stale check (every ~60 seconds at 2s poll interval)
            stale_check_counter += 1
            if stale_check_counter >= 30:
                self.reclaim_stale()
                stale_check_counter = 0

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
  # Auto-detect capabilities and start worker
  python pooled_job_worker.py

  # Process specific job types with custom concurrency
  python pooled_job_worker.py --job-types ocr,entity --max-concurrent 5

  # Show machine capabilities and recommended settings
  python pooled_job_worker.py --show-capabilities

  # Check for updates
  python pooled_job_worker.py --check-update
"""
    )
    parser.add_argument('--job-types', type=str, help='Comma-separated list of job types to process')
    parser.add_argument('--max-concurrent', type=int, default=None,
                        help='Maximum concurrent jobs (auto-detected if not specified)')
    parser.add_argument('--batch-size', type=int, default=5, help='Batch size for claiming jobs')
    parser.add_argument('--poll-interval', type=float, default=2.0, help='Poll interval in seconds')
    parser.add_argument('--stale-timeout', type=int, default=30, help='Stale job timeout in minutes')
    parser.add_argument('--db-url', type=str, help='Database URL (or set DATABASE_URL env var)')
    parser.add_argument('--no-update', action='store_true', help='Skip version check and auto-update')
    parser.add_argument('--check-update', action='store_true', help='Check for updates and exit')
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

    # Handle check-update mode
    if args.check_update:
        try:
            updater = AutoUpdater()
            update_available, local_hash, repo_hash = updater.check_for_updates()
            print(f"Local version:  {local_hash}")
            print(f"Repo version:   {repo_hash}")
            print(f"Update needed:  {'Yes' if update_available else 'No'}")
            if update_available:
                response = input("Apply update? [y/N] ")
                if response.lower() == 'y':
                    updater.update_and_restart()
            sys.exit(0)
        except Exception as e:
            print(f"Error checking for updates: {e}")
            sys.exit(1)

    # Check for updates before starting (unless --no-update)
    if not check_and_update(skip_update=args.no_update):
        # Worker restarted, exit this instance
        sys.exit(0)

    # Get database URL
    db_url = args.db_url or os.environ.get('DATABASE_URL')
    if not db_url:
        # Default for Epstein project - BobbyHomeEP via Tailscale
        db_url = "host=100.75.137.22 dbname=epstein_documents user=epstein_user password=epstein_secure_pw_2024"

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

    # Create worker
    worker = PooledJobWorker(
        db_url=db_url,
        job_types=job_types,
        max_concurrent=max_concurrent,
        batch_size=args.batch_size,
        poll_interval=args.poll_interval,
        stale_timeout_minutes=args.stale_timeout
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
