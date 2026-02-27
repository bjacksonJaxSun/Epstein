"""
Auto-scaling chunk+embed worker launcher.

Starts pooled_job_worker instances configured for chunk_embed jobs.
Can be run directly or submitted as a general job via the job pool.

Usage:
    python start_chunk_workers.py [--db-url URL] [--dry-run]
"""

import os
import sys
import subprocess
import socket
import argparse
import logging
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_DB_URL = "host=100.75.137.22 dbname=epstein_documents user=epstein_user password=epstein_secure_pw_2024"


def ensure_dependencies():
    """Install required packages if missing."""
    required = ['tiktoken', 'sentence_transformers']
    for pkg in required:
        try:
            __import__(pkg.replace('-', '_'))
        except ImportError:
            logger.info(f"Installing missing package: {pkg}")
            subprocess.run([sys.executable, '-m', 'pip', 'install', pkg],
                           check=True, capture_output=True)
            logger.info(f"Installed {pkg}")


def detect_capabilities():
    cpu_logical = os.cpu_count() or 2
    cpu_physical = cpu_logical
    mem_available_gb = 4.0

    try:
        import psutil
        cpu_physical = psutil.cpu_count(logical=False) or cpu_logical
        mem_available_gb = psutil.virtual_memory().available / (1024 ** 3)
    except ImportError:
        pass

    return cpu_physical, mem_available_gb


def main():
    parser = argparse.ArgumentParser(description='Auto-scaling chunk+embed worker launcher')
    parser.add_argument('--db-url', type=str, default=None)
    parser.add_argument('--instances', type=int, default=None)
    parser.add_argument('--max-concurrent', type=int, default=None)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    db_url = args.db_url or os.environ.get('DATABASE_URL', DEFAULT_DB_URL)

    ensure_dependencies()

    cpu_physical, mem_available_gb = detect_capabilities()
    hostname = socket.gethostname()
    logger.info(f"Machine: {hostname}, CPUs: {cpu_physical}, Mem available: {mem_available_gb:.1f}GB")

    # chunk_embed is heavier per job (model load + encode) — use fewer concurrent than extract
    usable_cores = max(1, cpu_physical - 1)
    usable_mem = max(0.5, mem_available_gb - 1.0)
    # Each chunk_embed uses ~1GB (model in memory) and 1 core
    target = min(usable_cores, int(usable_mem / 1.0))
    target = max(1, min(target, 12))

    jobs_per_instance = 2
    num_instances = args.instances or max(1, (target + jobs_per_instance - 1) // jobs_per_instance)
    max_concurrent = args.max_concurrent or max(1, target // num_instances)

    logger.info(f"Plan: {num_instances} instance(s) x {max_concurrent} concurrent = {num_instances * max_concurrent} total")

    worker_script = str(Path(__file__).parent / 'services' / 'pooled_job_worker.py')
    pids = []

    for i in range(num_instances):
        cmd = [
            sys.executable, worker_script,
            '--job-types', 'chunk_embed',
            '--max-concurrent', str(max_concurrent),
            '--batch-size', str(max_concurrent),
            '--db-url', db_url,
        ]

        if dry_run := args.dry_run:
            logger.info(f"[DRY RUN] Would run: {' '.join(cmd)}")
            continue

        if sys.platform == 'win32':
            proc = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            proc = subprocess.Popen(
                cmd,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        pids.append(proc.pid)
        logger.info(f"Started instance {i + 1}/{num_instances} (PID {proc.pid})")

    if pids:
        logger.info(f"Launched {len(pids)} chunk_embed worker(s): PIDs = {pids}")
        time.sleep(5)
        logger.info("Workers running in background.")

    return 0


if __name__ == '__main__':
    sys.exit(main())
