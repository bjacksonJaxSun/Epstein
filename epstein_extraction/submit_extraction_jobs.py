"""
Submit text extraction jobs to the job_pool.

Queries documents with extraction_status='pending' and r2_key set,
then submits them as 'extract_text' jobs for workers to pick up.

Usage:
    python submit_extraction_jobs.py                         # Submit all pending (datasets 1-10, 12)
    python submit_extraction_jobs.py --limit 10              # Submit first 10 for testing
    python submit_extraction_jobs.py --dataset 1,2,3         # Specific datasets only
    python submit_extraction_jobs.py --batch-size 500        # Control insert batch size
    python submit_extraction_jobs.py --dry-run               # Show counts without submitting
"""

import os
import sys
import json
import socket
import argparse
import logging
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Default datasets to process (1-10 and 12)
DEFAULT_DATASETS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12]


def get_db_url(args_db_url=None):
    """Resolve the database URL from args, env, or default."""
    if args_db_url:
        return args_db_url
    if os.environ.get('DATABASE_URL'):
        return os.environ['DATABASE_URL']
    # Default for Epstein project
    return "host=100.75.137.22 dbname=epstein_documents user=epstein_user password=epstein_secure_pw_2024"


def build_dataset_filter(datasets):
    """
    Build a WHERE clause fragment to filter by dataset number.

    Documents don't have a dataset_id column — the dataset is encoded in
    the r2_key prefix: 'DataSet_N/...'. We use LIKE patterns.
    """
    patterns = [f"DataSet_{d}/%" for d in datasets]
    clauses = " OR ".join(["r2_key LIKE %s"] * len(patterns))
    return f"({clauses})", patterns


def count_pending(conn, datasets):
    """Count pending documents matching the dataset filter."""
    ds_clause, ds_params = build_dataset_filter(datasets)
    sql = f"""
        SELECT COUNT(*)
        FROM documents
        WHERE extraction_status = 'pending'
          AND r2_key IS NOT NULL
          AND {ds_clause}
    """
    with conn.cursor() as cur:
        cur.execute(sql, ds_params)
        return cur.fetchone()[0]


def fetch_pending(conn, datasets, limit=None):
    """Fetch pending document IDs and r2_keys."""
    ds_clause, ds_params = build_dataset_filter(datasets)
    sql = f"""
        SELECT document_id, r2_key
        FROM documents
        WHERE extraction_status = 'pending'
          AND r2_key IS NOT NULL
          AND {ds_clause}
        ORDER BY document_id
    """
    params = ds_params[:]
    if limit:
        sql += " LIMIT %s"
        params.append(limit)

    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def submit_batch(conn, rows, priority=0, timeout_seconds=120):
    """
    Bulk-insert extraction jobs into job_pool using execute_values for speed.

    Returns the number of jobs inserted.
    """
    source_machine = socket.gethostname()

    values = []
    for document_id, r2_key in rows:
        payload = json.dumps({
            "action": "extract_text",
            "document_id": document_id,
            "r2_key": r2_key,
        })
        values.append((
            'extract_text',   # job_type
            payload,          # payload (JSONB)
            priority,
            timeout_seconds,
            source_machine,
        ))

    sql = """
        INSERT INTO job_pool (job_type, payload, priority, timeout_seconds, source_machine)
        VALUES %s
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, values, page_size=1000)
    conn.commit()

    return len(values)


def main():
    parser = argparse.ArgumentParser(
        description='Submit text extraction jobs to the job pool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--dataset', type=str, default=None,
                        help='Comma-separated dataset numbers (default: 1-10,12)')
    parser.add_argument('--batch-size', type=int, default=1000,
                        help='Insert batch size (default: 1000)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Max documents to submit (default: all)')
    parser.add_argument('--priority', type=int, default=0,
                        help='Job priority (default: 0)')
    parser.add_argument('--timeout', type=int, default=120,
                        help='Per-job timeout in seconds (default: 120)')
    parser.add_argument('--db-url', type=str, default=None,
                        help='Database URL (or set DATABASE_URL env var)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show counts without submitting')
    args = parser.parse_args()

    # Parse datasets
    if args.dataset:
        datasets = [int(d.strip()) for d in args.dataset.split(',')]
    else:
        datasets = DEFAULT_DATASETS

    db_url = get_db_url(args.db_url)
    logger.info(f"Datasets: {datasets}")

    conn = psycopg2.connect(db_url)

    try:
        # Show current counts
        total_pending = count_pending(conn, datasets)
        logger.info(f"Total pending documents with r2_key: {total_pending:,}")

        if total_pending == 0:
            logger.info("Nothing to submit.")
            return

        if args.dry_run:
            # Show per-dataset breakdown
            logger.info("--- Dry run — per-dataset breakdown ---")
            for ds in datasets:
                n = count_pending(conn, [ds])
                if n > 0:
                    logger.info(f"  DataSet_{ds}: {n:,} pending")
            return

        # Fetch rows
        effective_limit = args.limit if args.limit else total_pending
        logger.info(f"Fetching up to {effective_limit:,} rows...")
        rows = fetch_pending(conn, datasets, limit=args.limit)
        logger.info(f"Fetched {len(rows):,} documents")

        if not rows:
            return

        # Submit in batches
        total_submitted = 0
        batch_size = args.batch_size

        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            count = submit_batch(conn, batch, priority=args.priority,
                                 timeout_seconds=args.timeout)
            total_submitted += count
            logger.info(f"  Submitted batch {i // batch_size + 1}: "
                        f"{count} jobs (total: {total_submitted:,})")

        logger.info(f"Done. Submitted {total_submitted:,} extraction jobs.")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
