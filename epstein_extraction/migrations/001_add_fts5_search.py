"""
Migration: Add FTS5 Full-Text Search
Creates cleaned_text column and FTS5 virtual table for fast document search.
"""

import sqlite3
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import OUTPUT_DIR

DB_PATH = OUTPUT_DIR / "epstein_documents.db"


def check_column_exists(conn, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


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

    print("Starting FTS5 migration...")

    # Step 1: Add cleaned_text column if it doesn't exist
    if not check_column_exists(conn, 'documents', 'cleaned_text'):
        print("Adding cleaned_text column to documents table...")
        cursor.execute("ALTER TABLE documents ADD COLUMN cleaned_text TEXT")
        print("  Column added.")
    else:
        print("  cleaned_text column already exists.")

    # Step 2: Add redaction_count column if it doesn't exist
    if not check_column_exists(conn, 'documents', 'redaction_count'):
        print("Adding redaction_count column to documents table...")
        cursor.execute("ALTER TABLE documents ADD COLUMN redaction_count INTEGER DEFAULT 0")
        print("  Column added.")
    else:
        print("  redaction_count column already exists.")

    # Step 3: Create FTS5 virtual table
    if not check_table_exists(conn, 'documents_fts'):
        print("Creating FTS5 virtual table...")
        cursor.execute("""
            CREATE VIRTUAL TABLE documents_fts USING fts5(
                efta_number,
                document_title,
                full_text,
                cleaned_text,
                content='documents',
                content_rowid='document_id',
                tokenize='porter unicode61 remove_diacritics 1'
            )
        """)
        print("  FTS5 table created.")
    else:
        print("  documents_fts table already exists.")

    # Step 4: Create triggers to keep FTS in sync
    print("Creating sync triggers...")

    # Insert trigger
    cursor.execute("DROP TRIGGER IF EXISTS documents_fts_insert")
    cursor.execute("""
        CREATE TRIGGER documents_fts_insert AFTER INSERT ON documents BEGIN
            INSERT INTO documents_fts(rowid, efta_number, document_title, full_text, cleaned_text)
            VALUES (new.document_id, new.efta_number, new.document_title, new.full_text, new.cleaned_text);
        END
    """)

    # Delete trigger
    cursor.execute("DROP TRIGGER IF EXISTS documents_fts_delete")
    cursor.execute("""
        CREATE TRIGGER documents_fts_delete AFTER DELETE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, efta_number, document_title, full_text, cleaned_text)
            VALUES ('delete', old.document_id, old.efta_number, old.document_title, old.full_text, old.cleaned_text);
        END
    """)

    # Update trigger
    cursor.execute("DROP TRIGGER IF EXISTS documents_fts_update")
    cursor.execute("""
        CREATE TRIGGER documents_fts_update AFTER UPDATE ON documents BEGIN
            INSERT INTO documents_fts(documents_fts, rowid, efta_number, document_title, full_text, cleaned_text)
            VALUES ('delete', old.document_id, old.efta_number, old.document_title, old.full_text, old.cleaned_text);
            INSERT INTO documents_fts(rowid, efta_number, document_title, full_text, cleaned_text)
            VALUES (new.document_id, new.efta_number, new.document_title, new.full_text, new.cleaned_text);
        END
    """)
    print("  Triggers created.")

    conn.commit()
    print("Migration completed successfully!")


def migrate_down(conn):
    """Rollback migration."""
    cursor = conn.cursor()

    print("Rolling back FTS5 migration...")

    # Drop triggers
    cursor.execute("DROP TRIGGER IF EXISTS documents_fts_insert")
    cursor.execute("DROP TRIGGER IF EXISTS documents_fts_delete")
    cursor.execute("DROP TRIGGER IF EXISTS documents_fts_update")
    print("  Triggers dropped.")

    # Drop FTS table
    cursor.execute("DROP TABLE IF EXISTS documents_fts")
    print("  FTS5 table dropped.")

    # Note: SQLite doesn't support DROP COLUMN, so we leave the columns

    conn.commit()
    print("Rollback completed.")


def get_stats(conn):
    """Get current database stats."""
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM documents")
    doc_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM documents WHERE cleaned_text IS NOT NULL")
    cleaned_count = cursor.fetchone()[0]

    if check_table_exists(conn, 'documents_fts'):
        cursor.execute("SELECT COUNT(*) FROM documents_fts")
        fts_count = cursor.fetchone()[0]
    else:
        fts_count = 0

    return {
        'documents': doc_count,
        'cleaned': cleaned_count,
        'indexed': fts_count
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='FTS5 Search Migration')
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
        print(f"  Total documents: {stats['documents']:,}")
        print(f"  Cleaned text: {stats['cleaned']:,}")
        print(f"  FTS indexed: {stats['indexed']:,}")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
