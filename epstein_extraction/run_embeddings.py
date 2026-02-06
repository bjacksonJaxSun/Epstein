"""
Batch process document chunks to generate vector embeddings.
Run after the embeddings table migration and chunking.
"""

import sys
import time
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import OUTPUT_DIR, logger

DB_PATH = OUTPUT_DIR / "epstein_documents.db"
BATCH_SIZE = 64
DEFAULT_MODEL = 'all-MiniLM-L6-v2'


def check_embedding_support():
    """Check if embeddings are available."""
    try:
        from services.embedding_service import EmbeddingService, EMBEDDINGS_AVAILABLE
        return EMBEDDINGS_AVAILABLE
    except ImportError:
        return False


def get_chunks_to_embed(conn, model_name: str, limit: int = None) -> list:
    """Get chunks that haven't been embedded yet."""
    cursor = conn.cursor()

    sql = """
        SELECT c.chunk_id, c.chunk_text
        FROM document_chunks c
        LEFT JOIN chunk_embeddings e
            ON c.chunk_id = e.chunk_id AND e.model_name = ?
        WHERE e.chunk_id IS NULL
        ORDER BY c.document_id, c.chunk_index
    """

    if limit:
        sql += f" LIMIT {limit}"

    cursor.execute(sql, (model_name,))
    return cursor.fetchall()


def insert_embeddings(conn, embeddings: list, model_name: str, dimension: int) -> int:
    """Insert embeddings into the database."""
    if not embeddings:
        return 0

    cursor = conn.cursor()

    cursor.executemany("""
        INSERT OR REPLACE INTO chunk_embeddings (
            chunk_id, model_name, embedding, dimension
        ) VALUES (?, ?, ?, ?)
    """, [
        (chunk_id, model_name, emb.tobytes(), dimension)
        for chunk_id, emb in embeddings
    ])

    return len(embeddings)


def update_metadata(conn, model_name: str, dimension: int, count: int):
    """Update embedding metadata."""
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO embedding_metadata (model_name, dimension, chunks_embedded, last_updated)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(model_name) DO UPDATE SET
            chunks_embedded = chunks_embedded + excluded.chunks_embedded,
            last_updated = CURRENT_TIMESTAMP
    """, (model_name, dimension, count))


def get_stats(conn, model_name: str) -> dict:
    """Get current embedding stats."""
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM document_chunks")
    total_chunks = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM chunk_embeddings WHERE model_name = ?",
        (model_name,)
    )
    embedded = cursor.fetchone()[0]

    return {
        'total_chunks': total_chunks,
        'embedded': embedded,
        'pending': total_chunks - embedded,
    }


def process_batch(service, chunks: list) -> list:
    """Process a batch of chunks and generate embeddings."""
    texts = [text for _, text in chunks]
    chunk_ids = [cid for cid, _ in chunks]

    results = service.embed_batch(texts)

    return list(zip(chunk_ids, [r.embedding for r in results]))


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Generate embeddings for document chunks')
    parser.add_argument('--model', default=DEFAULT_MODEL, help='Embedding model name')
    parser.add_argument('--batch-size', type=int, default=BATCH_SIZE, help='Batch size')
    parser.add_argument('--limit', type=int, help='Limit chunks to process')
    args = parser.parse_args()

    # Check embedding support
    if not check_embedding_support():
        print("ERROR: sentence-transformers not installed.")
        print("Install with: pip install sentence-transformers")
        sys.exit(1)

    from services.embedding_service import EmbeddingService

    print(f"Database: {DB_PATH}")
    print(f"Model: {args.model}")

    # Initialize embedding service
    print("\nLoading embedding model...")
    start = time.time()
    service = EmbeddingService(model_name=args.model)
    print(f"  Model loaded in {time.time() - start:.1f}s")
    print(f"  Embedding dimension: {service.dimension}")

    conn = sqlite3.connect(str(DB_PATH), timeout=120)
    conn.execute("PRAGMA busy_timeout = 60000")

    try:
        stats = get_stats(conn, args.model)
        print(f"\nCurrent status:")
        print(f"  Total chunks: {stats['total_chunks']:,}")
        print(f"  Embedded: {stats['embedded']:,}")
        print(f"  Pending: {stats['pending']:,}")

        if stats['pending'] == 0:
            print("\nNo chunks need embedding.")
            return

        # Get chunks to process
        limit = args.limit or None
        chunks = get_chunks_to_embed(conn, args.model, limit)
        total_to_process = len(chunks)

        print(f"\nProcessing {total_to_process:,} chunks...")

        processed = 0
        start_time = time.time()

        # Process in batches
        for i in range(0, len(chunks), args.batch_size):
            batch = chunks[i:i + args.batch_size]

            embeddings = process_batch(service, batch)
            insert_embeddings(conn, embeddings, args.model, service.dimension)
            conn.commit()

            processed += len(batch)

            elapsed = time.time() - start_time
            rate = processed / elapsed if elapsed > 0 else 0

            print(f"  Progress: {processed:,}/{total_to_process:,} "
                  f"({100*processed/total_to_process:.1f}%) - "
                  f"{rate:.1f} chunks/sec")

        elapsed = time.time() - start_time

        # Update metadata
        update_metadata(conn, args.model, service.dimension, processed)
        conn.commit()

        print(f"\nEmbedding complete!")
        print(f"  Chunks processed: {processed:,}")
        print(f"  Time: {elapsed:.1f} seconds")
        print(f"  Rate: {processed/elapsed:.1f} chunks/sec")

        # Final stats
        stats = get_stats(conn, args.model)
        print(f"\nFinal status:")
        print(f"  Total embedded: {stats['embedded']:,}")
        print(f"  Pending: {stats['pending']:,}")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
