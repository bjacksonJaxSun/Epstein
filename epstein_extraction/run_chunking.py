"""
Batch process documents to create semantic chunks.
Run after the chunks table migration.
"""

import sys
import time
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import OUTPUT_DIR, logger
from services.document_chunker import SemanticChunker
from services.text_cleaner import TextCleaner

DB_PATH = OUTPUT_DIR / "epstein_documents.db"
BATCH_SIZE = 100


def get_documents_to_chunk(conn, limit: int = None) -> list:
    """Get documents that haven't been chunked yet."""
    cursor = conn.cursor()

    sql = """
        SELECT d.document_id, d.efta_number,
               COALESCE(d.cleaned_text, d.full_text) as text,
               d.page_count
        FROM documents d
        LEFT JOIN (
            SELECT DISTINCT document_id FROM document_chunks
        ) c ON d.document_id = c.document_id
        WHERE c.document_id IS NULL
        AND (d.full_text IS NOT NULL OR d.cleaned_text IS NOT NULL)
        ORDER BY d.document_id
    """

    if limit:
        sql += f" LIMIT {limit}"

    cursor.execute(sql)
    return cursor.fetchall()


def insert_chunks(conn, chunks: list) -> int:
    """Insert chunks into the database."""
    if not chunks:
        return 0

    cursor = conn.cursor()

    cursor.executemany("""
        INSERT OR REPLACE INTO document_chunks (
            chunk_id, document_id, efta_number, chunk_index,
            chunk_text, start_char, end_char, page_number,
            has_redaction, preceding_context, following_context, token_count
        ) VALUES (
            :chunk_id, :document_id, :efta_number, :chunk_index,
            :chunk_text, :start_char, :end_char, :page_number,
            :has_redaction, :preceding_context, :following_context, :token_count
        )
    """, [c.to_dict() for c in chunks])

    return len(chunks)


def rebuild_fts_index(conn):
    """Rebuild FTS index from existing chunks."""
    cursor = conn.cursor()

    print("Rebuilding FTS index...")

    # Clear and repopulate
    cursor.execute("DELETE FROM chunks_fts")
    cursor.execute("""
        INSERT INTO chunks_fts(rowid, chunk_id, efta_number, chunk_text)
        SELECT rowid, chunk_id, efta_number, chunk_text
        FROM document_chunks
    """)

    count = cursor.rowcount
    conn.commit()

    print(f"  Indexed {count:,} chunks")
    return count


def process_batch(
    conn,
    chunker: SemanticChunker,
    cleaner: TextCleaner,
    documents: list,
) -> tuple:
    """Process a batch of documents."""
    total_chunks = 0
    docs_processed = 0

    for doc_id, efta, text, page_count in documents:
        if not text:
            continue

        try:
            # Clean text if not already cleaned
            if cleaner:
                result = cleaner.clean_for_search(text)
                clean_text = result.cleaned_text
            else:
                clean_text = text

            # Create chunks
            chunks = chunker.chunk_document(
                document_id=doc_id,
                efta_number=efta,
                text=clean_text,
            )

            if chunks:
                insert_chunks(conn, chunks)
                total_chunks += len(chunks)

            docs_processed += 1

        except Exception as e:
            logger.debug(f"Error chunking {efta}: {e}")
            continue

    conn.commit()
    return docs_processed, total_chunks


def get_stats(conn) -> dict:
    """Get current chunking stats."""
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM documents WHERE full_text IS NOT NULL OR cleaned_text IS NOT NULL")
    total_docs = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT document_id) FROM document_chunks")
    chunked_docs = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM document_chunks")
    total_chunks = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM chunks_fts")
    indexed = cursor.fetchone()[0]

    return {
        'total_documents': total_docs,
        'chunked_documents': chunked_docs,
        'pending': total_docs - chunked_docs,
        'total_chunks': total_chunks,
        'fts_indexed': indexed,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Chunk documents for search and RAG')
    parser.add_argument('--batch-size', type=int, default=BATCH_SIZE, help='Batch size')
    parser.add_argument('--rebuild-fts', action='store_true', help='Rebuild FTS index only')
    parser.add_argument('--chunk-size', type=int, default=1000, help='Target chunk size')
    parser.add_argument('--overlap', type=int, default=100, help='Overlap between chunks')
    parser.add_argument('--limit', type=int, help='Limit documents to process')
    args = parser.parse_args()

    print(f"Database: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH), timeout=120)
    conn.execute("PRAGMA busy_timeout = 60000")

    try:
        stats = get_stats(conn)
        print(f"\nCurrent status:")
        print(f"  Total documents with text: {stats['total_documents']:,}")
        print(f"  Documents chunked: {stats['chunked_documents']:,}")
        print(f"  Pending: {stats['pending']:,}")
        print(f"  Total chunks: {stats['total_chunks']:,}")
        print(f"  FTS indexed: {stats['fts_indexed']:,}")

        if args.rebuild_fts:
            rebuild_fts_index(conn)
            return

        if stats['pending'] == 0:
            print("\nNo documents need chunking.")
            if stats['fts_indexed'] < stats['total_chunks']:
                rebuild_fts_index(conn)
            return

        # Initialize services
        chunker = SemanticChunker(
            target_chunk_size=args.chunk_size,
            overlap_size=args.overlap,
        )
        cleaner = TextCleaner()

        # Get documents to process
        limit = args.limit or None
        documents = get_documents_to_chunk(conn, limit)
        total_to_process = len(documents)

        print(f"\nProcessing {total_to_process:,} documents...")

        processed = 0
        total_chunks = 0
        start_time = time.time()

        # Process in batches
        for i in range(0, len(documents), args.batch_size):
            batch = documents[i:i + args.batch_size]

            docs_done, chunks_created = process_batch(conn, chunker, cleaner, batch)
            processed += docs_done
            total_chunks += chunks_created

            elapsed = time.time() - start_time
            rate = processed / elapsed if elapsed > 0 else 0

            print(f"  Progress: {processed:,}/{total_to_process:,} docs "
                  f"({100*processed/total_to_process:.1f}%) - "
                  f"{total_chunks:,} chunks - "
                  f"{rate:.1f} docs/sec")

        elapsed = time.time() - start_time
        print(f"\nChunking complete!")
        print(f"  Documents processed: {processed:,}")
        print(f"  Chunks created: {total_chunks:,}")
        print(f"  Time: {elapsed:.1f} seconds")
        print(f"  Avg chunks per doc: {total_chunks/processed:.1f}" if processed else "")

        # Rebuild FTS
        print()
        rebuild_fts_index(conn)

        # Final stats
        stats = get_stats(conn)
        print(f"\nFinal status:")
        print(f"  Documents chunked: {stats['chunked_documents']:,}")
        print(f"  Total chunks: {stats['total_chunks']:,}")
        print(f"  FTS indexed: {stats['fts_indexed']:,}")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
