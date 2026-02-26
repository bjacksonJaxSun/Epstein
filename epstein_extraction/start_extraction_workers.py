"""
Auto-scaling extraction worker launcher.

Detects machine capabilities and spawns the appropriate number of
pooled_job_worker instances for extract_text jobs.

Heuristic:
  - Each extraction job: ~500MB memory, 1 CPU core (mix of I/O + CPU)
  - Target concurrency = min(physical_cores, available_memory_gb // 0.5)
  - Split across instances: each instance gets max-concurrent = 3
  - Number of instances = ceil(target_concurrency / 3)

Can be run directly or submitted as a general job via the job pool.

Usage:
    python start_extraction_workers.py [--db-url URL] [--dry-run]
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


def detect_capabilities():
    """Detect machine specs using stdlib + optional psutil."""
    cpu_logical = os.cpu_count() or 2
    cpu_physical = cpu_logical  # fallback
    mem_total_gb = 8.0
    mem_available_gb = 4.0

    try:
        import psutil
        cpu_physical = psutil.cpu_count(logical=False) or cpu_logical
        mem = psutil.virtual_memory()
        mem_total_gb = mem.total / (1024**3)
        mem_available_gb = mem.available / (1024**3)
    except ImportError:
        # Fallback: parse /proc/meminfo on Linux or use WMI on Windows
        if sys.platform == 'win32':
            try:
                result = subprocess.run(
                    ['powershell', '-NoProfile', '-Command',
                     '(Get-CimInstance Win32_Processor).NumberOfCores;'
                     '(Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize;'
                     '(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory'],
                    capture_output=True, text=True, timeout=15
                )
                lines = result.stdout.strip().split('\n')
                if len(lines) >= 3:
                    cpu_physical = int(lines[0].strip())
                    mem_total_gb = int(lines[1].strip()) / (1024 * 1024)
                    mem_available_gb = int(lines[2].strip()) / (1024 * 1024)
            except Exception:
                pass
        else:
            try:
                with open('/proc/cpuinfo') as f:
                    cores = set()
                    for line in f:
                        if line.startswith('core id'):
                            cores.add(line.strip())
                    if cores:
                        cpu_physical = len(cores)
                with open('/proc/meminfo') as f:
                    for line in f:
                        if line.startswith('MemTotal:'):
                            mem_total_gb = int(line.split()[1]) / (1024 * 1024)
                        elif line.startswith('MemAvailable:'):
                            mem_available_gb = int(line.split()[1]) / (1024 * 1024)
            except Exception:
                pass

    return {
        'hostname': socket.gethostname(),
        'cpu_logical': cpu_logical,
        'cpu_physical': cpu_physical,
        'mem_total_gb': round(mem_total_gb, 1),
        'mem_available_gb': round(mem_available_gb, 1),
    }


def calculate_workers(caps):
    """
    Calculate optimal number of instances and concurrency per instance.

    Returns (num_instances, max_concurrent_per_instance)
    """
    # Budget: leave 1 core and 1GB for OS + main process
    usable_cores = max(1, caps['cpu_physical'] - 1)
    usable_memory_gb = max(0.5, caps['mem_available_gb'] - 1.0)

    # Each concurrent extraction uses ~0.5GB memory and 1 core
    mem_per_job = 0.5
    target_concurrency = min(usable_cores, int(usable_memory_gb / mem_per_job))
    target_concurrency = max(1, min(target_concurrency, 16))  # cap at 16

    # Split across instances, each handling 3 concurrent jobs
    jobs_per_instance = 3
    num_instances = max(1, (target_concurrency + jobs_per_instance - 1) // jobs_per_instance)

    # Adjust concurrency per instance if we rounded up
    concurrent_per = max(1, target_concurrency // num_instances)

    return num_instances, concurrent_per


def start_workers(num_instances, max_concurrent, db_url, dry_run=False):
    """Spawn worker processes in the background."""
    worker_script = str(Path(__file__).parent / 'services' / 'pooled_job_worker.py')
    python = sys.executable
    pids = []

    for i in range(num_instances):
        cmd = [
            python, worker_script,
            '--job-types', 'extract_text',
            '--max-concurrent', str(max_concurrent),
            '--batch-size', str(max_concurrent),
            '--db-url', db_url,
        ]

        if dry_run:
            logger.info(f"[DRY RUN] Would start instance {i+1}: {' '.join(cmd)}")
            continue

        # Spawn as a detached background process
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
        logger.info(f"Started instance {i+1}/{num_instances} (PID {proc.pid}, max_concurrent={max_concurrent})")

    return pids


def main():
    parser = argparse.ArgumentParser(description='Auto-scaling extraction worker launcher')
    parser.add_argument('--db-url', type=str, default=None)
    parser.add_argument('--dry-run', action='store_true', help='Show plan without starting workers')
    parser.add_argument('--instances', type=int, default=None, help='Override number of instances')
    parser.add_argument('--max-concurrent', type=int, default=None, help='Override concurrency per instance')
    args = parser.parse_args()

    db_url = args.db_url or os.environ.get('DATABASE_URL', DEFAULT_DB_URL)

    # Detect
    caps = detect_capabilities()
    logger.info(f"Machine: {caps['hostname']}")
    logger.info(f"CPUs: {caps['cpu_logical']} logical, {caps['cpu_physical']} physical")
    logger.info(f"Memory: {caps['mem_total_gb']}GB total, {caps['mem_available_gb']}GB available")

    # Calculate
    num_instances, concurrent_per = calculate_workers(caps)

    # Allow overrides
    if args.instances is not None:
        num_instances = args.instances
    if args.max_concurrent is not None:
        concurrent_per = args.max_concurrent

    total = num_instances * concurrent_per
    logger.info(f"Plan: {num_instances} instance(s) x {concurrent_per} concurrent = {total} total jobs")

    # Launch
    pids = start_workers(num_instances, concurrent_per, db_url, dry_run=args.dry_run)

    if pids:
        logger.info(f"Launched {len(pids)} worker(s): PIDs = {pids}")
        # Give them a moment to register heartbeats
        time.sleep(5)
        logger.info("Workers are running in background. Use live_workers view to monitor.")

    return 0


if __name__ == '__main__':
    sys.exit(main())
