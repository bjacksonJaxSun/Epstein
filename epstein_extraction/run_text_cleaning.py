"""
Batch process documents to clean text and populate FTS index.
Run after the migration to index all existing documents.
"""

import sys
import time
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import OUTPUT_DIR, logger
from services.text_cleaner import TextCleaner

DB_PATH = OUTPUT_DIR / "epstein_documents.db"
BATCH_SIZE = 500


def populate_fts_index(conn):
    """Populate FTS index from existing documents."""
    cursor = conn.cursor()

    print("Rebuilding FTS index from existing documents...")

    # Clear existing FTS data
    cursor.execute("DELETE FROM documents_fts")

    # Insert all documents into FTS
    cursor.execute("""
        INSERT INTO documents_fts(rowid, efta_number, document_title, full_text, cleaned_text)
        SELECT document_id, efta_number, document_title, full_text, cleaned_text
        FROM documents
        WHERE full_text IS NOT NULL OR cleaned_text IS NOT NULL
    """)

    count = cursor.rowcount
    conn.commit()

    print(f"  Indexed {count:,} documents in FTS")
    return count


def process_batch(conn, cleaner: TextCleaner, offset: int, limit: int) -> int:
    """Process a batch of documents."""
    cursor = conn.cursor()

    # Get batch of documents that need cleaning
    cursor.execute("""
        SELECT document_id, full_text
        FROM documents
        WHERE full_text IS NOT NULL
        AND cleaned_text IS NULL
        ORDER BY document_id
        LIMIT ? OFFSET ?
    """, (limit, offset))

    rows = cursor.fetchall()
    if not rows:
        return 0

    updates = []
    for doc_id, full_text in rows:
        if full_text:
            result = cleaner.clean_for_search(full_text)
            updates.append((result.cleaned_text, result.redaction_count, doc_id))
        else:
            updates.append(('', 0, doc_id))

    # Batch update
    cursor.executemany("""
        UPDATE documents
        SET cleaned_text = ?, redaction_count = ?
        WHERE document_id = ?
    """, updates)

    conn.commit()
    return len(updates)


def get_counts(conn) -> dict:
    """Get processing counts."""
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM documents")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM documents WHERE full_text IS NOT NULL")
    with_text = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM documents WHERE cleaned_text IS NOT NULL")
    cleaned = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM documents_fts")
    indexed = cursor.fetchone()[0]

    return {
        'total': total,
        'with_text': with_text,
        'cleaned': cleaned,
        'indexed': indexed,
        'pending': with_text - cleaned
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Clean document text and build FTS index')
    parser.add_argument('--rebuild-fts', action='store_true', help='Rebuild FTS index only')
    parser.add_argument('--batch-size', type=int, default=BATCH_SIZE, help='Batch size')
    args = parser.parse_args()

    print(f"Database: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH), timeout=120)
    conn.execute("PRAGMA busy_timeout = 60000")  # 60 second timeout for locks

    try:
        counts = get_counts(conn)
        print(f"\nCurrent status:")
        print(f"  Total documents: {counts['total']:,}")
        print(f"  With text: {counts['with_text']:,}")
        print(f"  Cleaned: {counts['cleaned']:,}")
        print(f"  Pending: {counts['pending']:,}")
        print(f"  FTS indexed: {counts['indexed']:,}")

        if args.rebuild_fts:
            populate_fts_index(conn)
            return

        if counts['pending'] == 0:
            print("\nNo documents need cleaning.")
            if counts['indexed'] < counts['cleaned']:
                print("Rebuilding FTS index...")
                populate_fts_index(conn)
            return

        # Process documents
        cleaner = TextCleaner()
        processed = 0
        start_time = time.time()

        print(f"\nProcessing {counts['pending']:,} documents...")

        while True:
            batch_count = process_batch(conn, cleaner, 0, args.batch_size)
            if batch_count == 0:
                break

            processed += batch_count
            elapsed = time.time() - start_time
            rate = processed / elapsed if elapsed > 0 else 0

            print(f"  Processed {processed:,}/{counts['pending']:,} "
                  f"({100*processed/counts['pending']:.1f}%) - "
                  f"{rate:.1f} docs/sec")

        elapsed = time.time() - start_time
        print(f"\nText cleaning complete!")
        print(f"  Processed: {processed:,} documents")
        print(f"  Time: {elapsed:.1f} seconds")
        print(f"  Rate: {processed/elapsed:.1f} docs/sec")

        # Rebuild FTS index
        print("\nRebuilding FTS index...")
        populate_fts_index(conn)

        # Final stats
        counts = get_counts(conn)
        print(f"\nFinal status:")
        print(f"  Cleaned: {counts['cleaned']:,}")
        print(f"  FTS indexed: {counts['indexed']:,}")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
