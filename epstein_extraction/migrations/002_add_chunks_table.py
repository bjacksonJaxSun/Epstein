"""
Migration: Add Document Chunks Table
Creates document_chunks table and FTS5 index for chunk-level search.
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

    print("Starting chunks table migration...")

    # Step 1: Create document_chunks table
    if not check_table_exists(conn, 'document_chunks'):
        print("Creating document_chunks table...")
        cursor.execute("""
            CREATE TABLE document_chunks (
                chunk_id TEXT PRIMARY KEY,
                document_id INTEGER NOT NULL,
                efta_number TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                start_char INTEGER NOT NULL,
                end_char INTEGER NOT NULL,
                page_number INTEGER,
                has_redaction BOOLEAN DEFAULT FALSE,
                preceding_context TEXT,
                following_context TEXT,
                token_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (document_id) REFERENCES documents(document_id)
            )
        """)
        print("  Table created.")

        # Create indexes
        print("Creating indexes...")
        cursor.execute("CREATE INDEX idx_chunks_document ON document_chunks(document_id)")
        cursor.execute("CREATE INDEX idx_chunks_efta ON document_chunks(efta_number)")
        cursor.execute("CREATE INDEX idx_chunks_page ON document_chunks(page_number)")
        cursor.execute("CREATE INDEX idx_chunks_redaction ON document_chunks(has_redaction)")
        cursor.execute("CREATE INDEX idx_chunks_index ON document_chunks(document_id, chunk_index)")
        print("  Indexes created.")
    else:
        print("  document_chunks table already exists.")

    # Step 2: Create FTS5 virtual table for chunks
    if not check_table_exists(conn, 'chunks_fts'):
        print("Creating chunks_fts FTS5 table...")
        cursor.execute("""
            CREATE VIRTUAL TABLE chunks_fts USING fts5(
                chunk_id,
                efta_number,
                chunk_text,
                content='document_chunks',
                content_rowid='rowid',
                tokenize='porter unicode61 remove_diacritics 1'
            )
        """)
        print("  FTS5 table created.")

        # Create triggers to keep FTS in sync
        print("Creating sync triggers...")

        cursor.execute("DROP TRIGGER IF EXISTS chunks_fts_insert")
        cursor.execute("""
            CREATE TRIGGER chunks_fts_insert AFTER INSERT ON document_chunks BEGIN
                INSERT INTO chunks_fts(rowid, chunk_id, efta_number, chunk_text)
                VALUES (new.rowid, new.chunk_id, new.efta_number, new.chunk_text);
            END
        """)

        cursor.execute("DROP TRIGGER IF EXISTS chunks_fts_delete")
        cursor.execute("""
            CREATE TRIGGER chunks_fts_delete AFTER DELETE ON document_chunks BEGIN
                INSERT INTO chunks_fts(chunks_fts, rowid, chunk_id, efta_number, chunk_text)
                VALUES ('delete', old.rowid, old.chunk_id, old.efta_number, old.chunk_text);
            END
        """)

        cursor.execute("DROP TRIGGER IF EXISTS chunks_fts_update")
        cursor.execute("""
            CREATE TRIGGER chunks_fts_update AFTER UPDATE ON document_chunks BEGIN
                INSERT INTO chunks_fts(chunks_fts, rowid, chunk_id, efta_number, chunk_text)
                VALUES ('delete', old.rowid, old.chunk_id, old.efta_number, old.chunk_text);
                INSERT INTO chunks_fts(rowid, chunk_id, efta_number, chunk_text)
                VALUES (new.rowid, new.chunk_id, new.efta_number, new.chunk_text);
            END
        """)
        print("  Triggers created.")
    else:
        print("  chunks_fts table already exists.")

    conn.commit()
    print("Migration completed successfully!")


def migrate_down(conn):
    """Rollback migration."""
    cursor = conn.cursor()

    print("Rolling back chunks migration...")

    # Drop triggers
    cursor.execute("DROP TRIGGER IF EXISTS chunks_fts_insert")
    cursor.execute("DROP TRIGGER IF EXISTS chunks_fts_delete")
    cursor.execute("DROP TRIGGER IF EXISTS chunks_fts_update")
    print("  Triggers dropped.")

    # Drop FTS table
    cursor.execute("DROP TABLE IF EXISTS chunks_fts")
    print("  chunks_fts table dropped.")

    # Drop chunks table
    cursor.execute("DROP TABLE IF EXISTS document_chunks")
    print("  document_chunks table dropped.")

    conn.commit()
    print("Rollback completed.")


def get_stats(conn):
    """Get current chunk stats."""
    cursor = conn.cursor()

    stats = {}

    if check_table_exists(conn, 'document_chunks'):
        cursor.execute("SELECT COUNT(*) FROM document_chunks")
        stats['chunks'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT document_id) FROM document_chunks")
        stats['documents_chunked'] = cursor.fetchone()[0]

        cursor.execute("SELECT AVG(token_count) FROM document_chunks")
        avg = cursor.fetchone()[0]
        stats['avg_tokens_per_chunk'] = round(avg, 1) if avg else 0
    else:
        stats['chunks'] = 0
        stats['documents_chunked'] = 0
        stats['avg_tokens_per_chunk'] = 0

    if check_table_exists(conn, 'chunks_fts'):
        cursor.execute("SELECT COUNT(*) FROM chunks_fts")
        stats['fts_indexed'] = cursor.fetchone()[0]
    else:
        stats['fts_indexed'] = 0

    cursor.execute("SELECT COUNT(*) FROM documents")
    stats['total_documents'] = cursor.fetchone()[0]

    return stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Document Chunks Migration')
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
        print(f"  Total documents: {stats['total_documents']:,}")
        print(f"  Documents chunked: {stats['documents_chunked']:,}")
        print(f"  Total chunks: {stats['chunks']:,}")
        print(f"  Avg tokens/chunk: {stats['avg_tokens_per_chunk']}")
        print(f"  FTS indexed: {stats['fts_indexed']:,}")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
