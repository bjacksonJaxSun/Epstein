"""
Migration: Add Chunk Embeddings Table
Creates chunk_embeddings table for vector similarity search.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import OUTPUT_DIR

DB_PATH = OUTPUT_DIR / "epstein_documents.db"


def check_table_exists(conn, table: str) -> bool:
    """Check if a table exists."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    )
    return cursor.fetchone() is not None


def migrate_up(conn):
    """Apply migration."""
    cursor = conn.cursor()

    print("Starting chunk embeddings migration...")

    # Step 1: Create chunk_embeddings table
    if not check_table_exists(conn, 'chunk_embeddings'):
        print("Creating chunk_embeddings table...")
        cursor.execute("""
            CREATE TABLE chunk_embeddings (
                chunk_id TEXT PRIMARY KEY,
                model_name TEXT NOT NULL,
                embedding BLOB NOT NULL,
                dimension INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (chunk_id) REFERENCES document_chunks(chunk_id)
            )
        """)
        print("  Table created.")

        # Create indexes
        print("Creating indexes...")
        cursor.execute("CREATE INDEX idx_embeddings_model ON chunk_embeddings(model_name)")
        print("  Indexes created.")
    else:
        print("  chunk_embeddings table already exists.")

    # Step 2: Create embedding metadata table
    if not check_table_exists(conn, 'embedding_metadata'):
        print("Creating embedding_metadata table...")
        cursor.execute("""
            CREATE TABLE embedding_metadata (
                id INTEGER PRIMARY KEY,
                model_name TEXT NOT NULL UNIQUE,
                dimension INTEGER NOT NULL,
                chunks_embedded INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("  Table created.")
    else:
        print("  embedding_metadata table already exists.")

    conn.commit()
    print("Migration completed successfully!")


def migrate_down(conn):
    """Rollback migration."""
    cursor = conn.cursor()

    print("Rolling back chunk embeddings migration...")

    # Drop tables
    cursor.execute("DROP TABLE IF EXISTS chunk_embeddings")
    print("  chunk_embeddings table dropped.")

    cursor.execute("DROP TABLE IF EXISTS embedding_metadata")
    print("  embedding_metadata table dropped.")

    conn.commit()
    print("Rollback completed.")


def get_stats(conn):
    """Get current embedding stats."""
    cursor = conn.cursor()

    stats = {}

    if check_table_exists(conn, 'chunk_embeddings'):
        cursor.execute("SELECT COUNT(*) FROM chunk_embeddings")
        stats['embeddings'] = cursor.fetchone()[0]

        cursor.execute("SELECT DISTINCT model_name FROM chunk_embeddings")
        stats['models'] = [row[0] for row in cursor.fetchall()]
    else:
        stats['embeddings'] = 0
        stats['models'] = []

    if check_table_exists(conn, 'document_chunks'):
        cursor.execute("SELECT COUNT(*) FROM document_chunks")
        stats['total_chunks'] = cursor.fetchone()[0]
    else:
        stats['total_chunks'] = 0

    stats['pending'] = stats['total_chunks'] - stats['embeddings']

    return stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Chunk Embeddings Migration')
    parser.add_argument('action', choices=['up', 'down', 'status'], help='Migration action')
    args = parser.parse_args()

    print(f"Database: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH), timeout=60)

    try:
        if args.action == 'up':
            migrate_up(conn)
        elif args.action == 'down':
            migrate_down(conn)

        # Show stats
        stats = get_stats(conn)
        print(f"\nDatabase stats:")
        print(f"  Total chunks: {stats['total_chunks']:,}")
        print(f"  Chunks with embeddings: {stats['embeddings']:,}")
        print(f"  Pending: {stats['pending']:,}")
        print(f"  Models used: {', '.join(stats['models']) if stats['models'] else 'None'}")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
