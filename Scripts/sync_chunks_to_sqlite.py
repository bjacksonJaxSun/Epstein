#!/usr/bin/env python3
"""
Sync document chunks from PostgreSQL (VM) to SQLite (local dashboard database)
Creates FTS5 index for full-text search in the dashboard.
"""

import sqlite3
import psycopg2
import os
from pathlib import Path

# Configuration
SQLITE_DB_PATH = r"C:\Development\EpsteinDownloader\extraction_output\epstein_documents.db"
PG_HOST = "20.25.96.123"
PG_PORT = 5432
PG_DATABASE = "epstein_documents"
PG_USER = "epstein_user"
PG_PASSWORD = "epstein_secure_pw_2024"

BATCH_SIZE = 10000


def connect_postgres():
    """Connect to PostgreSQL database on VM"""
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        database=PG_DATABASE,
        user=PG_USER,
        password=PG_PASSWORD
    )


def connect_sqlite():
    """Connect to local SQLite database"""
    return sqlite3.connect(SQLITE_DB_PATH)


def setup_sqlite_tables(sqlite_conn):
    """Create document_chunks table if not exists"""
    cursor = sqlite_conn.cursor()

    # Create document_chunks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_chunks (
            chunk_id INTEGER PRIMARY KEY,
            document_id INTEGER NOT NULL,
            efta_number TEXT,
            chunk_index INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            chunk_tokens INTEGER,
            start_char INTEGER,
            end_char INTEGER,
            page_number INTEGER,
            has_redaction INTEGER DEFAULT 0,
            preceding_context TEXT,
            following_context TEXT,
            created_at TEXT,
            FOREIGN KEY (document_id) REFERENCES documents(document_id)
        )
    """)

    # Create indexes
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON document_chunks(document_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunks_chunk_index ON document_chunks(chunk_index)
    """)

    sqlite_conn.commit()
    print("SQLite tables and indexes created/verified")


def setup_fts5(sqlite_conn):
    """Create FTS5 virtual table for full-text search"""
    cursor = sqlite_conn.cursor()

    # Drop existing FTS table if exists
    cursor.execute("DROP TABLE IF EXISTS chunks_fts")

    # Create FTS5 virtual table
    cursor.execute("""
        CREATE VIRTUAL TABLE chunks_fts USING fts5(
            efta_number,
            chunk_text,
            content='document_chunks',
            content_rowid='chunk_id'
        )
    """)

    sqlite_conn.commit()
    print("FTS5 virtual table created")


def sync_chunks(pg_conn, sqlite_conn):
    """Sync chunks from PostgreSQL to SQLite"""
    pg_cursor = pg_conn.cursor()
    sqlite_cursor = sqlite_conn.cursor()

    # Get count from PostgreSQL (valid chunks only)
    pg_cursor.execute("SELECT COUNT(*) FROM document_chunks WHERE chunk_index >= 0")
    total_pg = pg_cursor.fetchone()[0]
    print(f"Total valid chunks in PostgreSQL: {total_pg:,}")

    # Clear existing chunks in SQLite
    sqlite_cursor.execute("DELETE FROM document_chunks")
    sqlite_conn.commit()
    print("Cleared existing chunks in SQLite")

    # Fetch and insert in batches
    offset = 0
    total_inserted = 0

    while offset < total_pg:
        pg_cursor.execute("""
            SELECT
                chunk_id,
                document_id,
                (SELECT efta_number FROM documents d WHERE d.document_id = dc.document_id) as efta_number,
                chunk_index,
                chunk_text,
                chunk_tokens,
                start_char,
                end_char,
                created_at::text
            FROM document_chunks dc
            WHERE chunk_index >= 0
            ORDER BY chunk_id
            LIMIT %s OFFSET %s
        """, (BATCH_SIZE, offset))

        rows = pg_cursor.fetchall()
        if not rows:
            break

        # Insert into SQLite
        sqlite_cursor.executemany("""
            INSERT INTO document_chunks
            (chunk_id, document_id, efta_number, chunk_index, chunk_text,
             chunk_tokens, start_char, end_char, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)

        sqlite_conn.commit()
        total_inserted += len(rows)
        offset += BATCH_SIZE

        print(f"Synced: {total_inserted:,}/{total_pg:,} chunks ({100*total_inserted/total_pg:.1f}%)")

    print(f"Sync complete: {total_inserted:,} chunks transferred")
    return total_inserted


def populate_fts5(sqlite_conn):
    """Populate the FTS5 index from document_chunks"""
    cursor = sqlite_conn.cursor()

    print("Populating FTS5 index...")

    # Populate FTS5 table
    cursor.execute("""
        INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')
    """)

    sqlite_conn.commit()

    # Verify count
    cursor.execute("SELECT COUNT(*) FROM chunks_fts")
    fts_count = cursor.fetchone()[0]
    print(f"FTS5 index populated: {fts_count:,} entries")


def main():
    print("=" * 60)
    print("Syncing document chunks from PostgreSQL to SQLite")
    print("=" * 60)

    # Check SQLite database exists
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"ERROR: SQLite database not found: {SQLITE_DB_PATH}")
        return

    print(f"SQLite database: {SQLITE_DB_PATH}")
    print(f"PostgreSQL: {PG_HOST}:{PG_PORT}/{PG_DATABASE}")
    print()

    try:
        # Connect to databases
        print("Connecting to PostgreSQL...")
        pg_conn = connect_postgres()
        print("Connected to PostgreSQL")

        print("Connecting to SQLite...")
        sqlite_conn = connect_sqlite()
        print("Connected to SQLite")
        print()

        # Setup tables
        setup_sqlite_tables(sqlite_conn)
        print()

        # Sync chunks
        total_synced = sync_chunks(pg_conn, sqlite_conn)
        print()

        if total_synced > 0:
            # Create FTS5 index
            setup_fts5(sqlite_conn)
            populate_fts5(sqlite_conn)

        print()
        print("=" * 60)
        print("Sync complete!")
        print("=" * 60)

        # Final stats
        cursor = sqlite_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM document_chunks")
        total_chunks = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM chunks_fts")
        fts_count = cursor.fetchone()[0]

        print(f"Total chunks in SQLite: {total_chunks:,}")
        print(f"FTS5 indexed chunks: {fts_count:,}")

        pg_conn.close()
        sqlite_conn.close()

    except Exception as e:
        print(f"ERROR: {e}")
        raise


if __name__ == "__main__":
    main()
