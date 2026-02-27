"""
Submit chunk+embed jobs to the job_pool for documents that have text but no chunks.

Queries documents where full_text or video_transcript exists but no
document_chunks rows, then submits 'chunk_embed' jobs for workers to pick up.

Usage:
    python submit_chunk_embed_jobs.py                    # Submit all missing
    python submit_chunk_embed_jobs.py --limit 10         # Submit first 10 for testing
    python submit_chunk_embed_jobs.py --dry-run           # Show counts without submitting
    python submit_chunk_embed_jobs.py --batch-size 500    # Control insert batch size
"""

import os
import sys
import json
import socket
import argparse
import logging

import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def get_db_url(args_db_url=None):
    """Resolve the database URL from args, env, or default."""
    if args_db_url:
        return args_db_url
    if os.environ.get('DATABASE_URL'):
        return os.environ['DATABASE_URL']
    # Default for Epstein project - BobbyHomeEP via Tailscale
    return "host=100.75.137.22 dbname=epstein_documents user=epstein_user password=epstein_secure_pw_2024"


def count_needing_chunks(conn):
    """Count documents that have text but no chunks."""
    sql = """
        SELECT COUNT(*) FROM documents d
        WHERE NOT EXISTS (SELECT 1 FROM document_chunks c WHERE c.document_id = d.document_id)
        AND ((d.full_text IS NOT NULL AND LENGTH(d.full_text) > 50)
             OR (d.video_transcript IS NOT NULL AND LENGTH(d.video_transcript) > 10))
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchone()[0]


def fetch_needing_chunks(conn, limit=None):
    """Fetch document IDs that have text but no chunks."""
    sql = """
        SELECT d.document_id FROM documents d
        WHERE NOT EXISTS (SELECT 1 FROM document_chunks c WHERE c.document_id = d.document_id)
        AND ((d.full_text IS NOT NULL AND LENGTH(d.full_text) > 50)
             OR (d.video_transcript IS NOT NULL AND LENGTH(d.video_transcript) > 10))
        ORDER BY d.document_id
    """
    params = []
    if limit:
        sql += " LIMIT %s"
        params.append(limit)

    with conn.cursor() as cur:
        cur.execute(sql, params)
        return [row[0] for row in cur.fetchall()]


def submit_batch(conn, document_ids, priority=0, timeout_seconds=120):
    """
    Bulk-insert chunk_embed jobs into job_pool using execute_values.

    Returns the number of jobs inserted.
    """
    source_machine = socket.gethostname()

    values = []
    for document_id in document_ids:
        payload = json.dumps({
            "action": "chunk_embed",
            "document_id": document_id,
        })
        values.append((
            'chunk_embed',     # job_type
            payload,           # payload (JSONB)
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
        description='Submit chunk+embed jobs for documents with text but no chunks',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
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

    db_url = get_db_url(args.db_url)
    conn = psycopg2.connect(db_url)

    try:
        total_needing = count_needing_chunks(conn)
        logger.info(f"Documents with text but no chunks: {total_needing:,}")

        if total_needing == 0:
            logger.info("Nothing to submit.")
            return

        if args.dry_run:
            logger.info("Dry run — no jobs submitted.")
            return

        # Fetch document IDs
        effective_limit = args.limit if args.limit else total_needing
        logger.info(f"Fetching up to {effective_limit:,} document IDs...")
        doc_ids = fetch_needing_chunks(conn, limit=args.limit)
        logger.info(f"Fetched {len(doc_ids):,} documents")

        if not doc_ids:
            return

        # Submit in batches
        total_submitted = 0
        batch_size = args.batch_size

        for i in range(0, len(doc_ids), batch_size):
            batch = doc_ids[i:i + batch_size]
            count = submit_batch(conn, batch, priority=args.priority,
                                 timeout_seconds=args.timeout)
            total_submitted += count
            logger.info(f"  Submitted batch {i // batch_size + 1}: "
                        f"{count} jobs (total: {total_submitted:,})")

        logger.info(f"Done. Submitted {total_submitted:,} chunk_embed jobs.")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
