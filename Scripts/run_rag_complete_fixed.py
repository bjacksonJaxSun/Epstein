#!/usr/bin/env python3
"""
Complete RAG Pipeline - Fixed version
Tracks processed documents via marker chunks to avoid infinite loop
"""

import time
import psycopg2
from psycopg2.extras import execute_batch
import tiktoken
from sentence_transformers import SentenceTransformer
from loguru import logger

DB_CONFIG = {
    'dbname': 'epstein_documents',
    'user': 'epstein_user',
    'password': 'epstein_secure_pw_2024',
    'host': 'localhost'
}

CHUNK_SIZE = 600
CHUNK_OVERLAP = 100
MIN_CHUNK_SIZE = 30

BATCH_SIZE = 500
EMBEDDING_BATCH_SIZE = 64

encoding = tiktoken.get_encoding('cl100k_base')

logger.info('Loading embedding model...')
model = SentenceTransformer('all-MiniLM-L6-v2')
logger.info('Model loaded')


def count_tokens(text):
    if not text:
        return 0
    return len(encoding.encode(text))


def chunk_text(text):
    if not text or not text.strip():
        return []

    text = text.strip()
    token_count = count_tokens(text)

    if token_count <= MIN_CHUNK_SIZE:
        return []

    if token_count <= CHUNK_SIZE:
        return [{'text': text, 'tokens': token_count, 'start_char': 0, 'end_char': len(text)}]

    tokens = encoding.encode(text)
    chunks = []
    start = 0

    while start < len(tokens):
        end = min(start + CHUNK_SIZE, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text_decoded = encoding.decode(chunk_tokens)

        chunks.append({
            'text': chunk_text_decoded.strip(),
            'tokens': len(chunk_tokens),
            'start_char': start * 4,
            'end_char': min(end * 4, len(text))
        })

        if end >= len(tokens):
            break
        start = end - CHUNK_OVERLAP

    return chunks


def combine_document_text(full_text, video_transcript):
    parts = []

    if full_text and len(full_text.strip()) > 30:
        parts.append(full_text.strip())

    if video_transcript and len(video_transcript.strip()) > 10:
        if video_transcript.strip() not in ['[No speech detected]', '']:
            parts.append('\n\n--- TRANSCRIPT ---\n' + video_transcript.strip())

    return '\n\n'.join(parts) if parts else None


def generate_embeddings(texts):
    if not texts:
        return []
    embeddings = model.encode(texts, show_progress_bar=False)
    return embeddings.tolist()


def main():
    logger.info('Starting Complete RAG Pipeline (Fixed)')

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    # Get documents that need processing
    cur.execute("""
        SELECT d.document_id FROM documents d
        WHERE NOT EXISTS (SELECT 1 FROM document_chunks c WHERE c.document_id = d.document_id)
        AND ((d.full_text IS NOT NULL AND LENGTH(d.full_text) > 50)
            OR (d.video_transcript IS NOT NULL AND LENGTH(d.video_transcript) > 10))
    """)
    docs_to_process = [row[0] for row in cur.fetchall()]
    total_to_chunk = len(docs_to_process)

    logger.info(f'Documents to chunk: {total_to_chunk:,}')

    if total_to_chunk == 0:
        logger.info('No documents to chunk')
    else:
        # Phase 1: Chunking
        logger.info('=== Phase 1: Chunking ===')
        processed = 0
        total_chunks = 0
        start_time = time.time()

        for i in range(0, len(docs_to_process), BATCH_SIZE):
            batch_ids = docs_to_process[i:i+BATCH_SIZE]

            cur.execute("""
                SELECT d.document_id, d.efta_number, d.full_text, d.video_transcript
                FROM documents d
                WHERE d.document_id = ANY(%s)
            """, (batch_ids,))

            rows = cur.fetchall()
            chunk_inserts = []
            marker_inserts = []

            for doc_id, efta, full_text, transcript in rows:
                combined_text = combine_document_text(full_text, transcript)

                if combined_text:
                    chunks = chunk_text(combined_text)
                    if chunks:
                        for idx, c in enumerate(chunks):
                            chunk_inserts.append((doc_id, idx, c['text'], c['tokens'], c['start_char'], c['end_char']))
                    else:
                        # Marker with empty string for docs with text but no valid chunks
                        marker_inserts.append((doc_id, -1, '[NO_CHUNKS]', 0, 0, 0))
                else:
                    # Marker for docs without valid text
                    marker_inserts.append((doc_id, -1, '[NO_TEXT]', 0, 0, 0))

                processed += 1

            if chunk_inserts:
                execute_batch(cur, """
                    INSERT INTO document_chunks
                    (document_id, chunk_index, chunk_text, chunk_tokens, start_char, end_char)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, chunk_inserts)
                total_chunks += len(chunk_inserts)

            if marker_inserts:
                execute_batch(cur, """
                    INSERT INTO document_chunks
                    (document_id, chunk_index, chunk_text, chunk_tokens, start_char, end_char)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, marker_inserts)

            if processed % 5000 == 0 or processed == total_to_chunk:
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                logger.info(f'Chunking: {processed:,}/{total_to_chunk:,} - {total_chunks:,} chunks - {rate:.1f} docs/sec')

        logger.info(f'Chunking complete: {processed:,} docs, {total_chunks:,} new chunks')

    # Phase 2: Embeddings
    logger.info('=== Phase 2: Generating Embeddings ===')

    cur.execute('SELECT COUNT(*) FROM document_chunks WHERE embedding_vector IS NULL AND chunk_index >= 0')
    chunks_need_embeddings = cur.fetchone()[0]
    logger.info(f'Chunks needing embeddings: {chunks_need_embeddings:,}')

    if chunks_need_embeddings == 0:
        logger.info('No chunks need embeddings')
    else:
        embedded = 0
        start_time = time.time()

        while True:
            cur.execute("""
                SELECT chunk_id, chunk_text FROM document_chunks
                WHERE embedding_vector IS NULL AND chunk_index >= 0
                ORDER BY chunk_id
                LIMIT %s
            """, (EMBEDDING_BATCH_SIZE,))

            rows = cur.fetchall()
            if not rows:
                break

            chunk_ids = [r[0] for r in rows]
            texts = [r[1] for r in rows]

            embeddings = generate_embeddings(texts)

            for chunk_id, embedding in zip(chunk_ids, embeddings):
                cur.execute('UPDATE document_chunks SET embedding_vector = %s WHERE chunk_id = %s', (embedding, chunk_id))

            embedded += len(rows)

            if embedded % 1000 == 0 or embedded == chunks_need_embeddings:
                elapsed = time.time() - start_time
                rate = embedded / elapsed if elapsed > 0 else 0
                logger.info(f'Embeddings: {embedded:,}/{chunks_need_embeddings:,} - {rate:.1f} chunks/sec')

        logger.info(f'Embeddings complete: {embedded:,} chunks')

    # Final stats
    cur.execute('SELECT COUNT(*) FROM document_chunks WHERE chunk_index >= 0')
    total_valid = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM document_chunks WHERE embedding_vector IS NOT NULL')
    total_embedded = cur.fetchone()[0]

    logger.info('=== RAG Pipeline Complete ===')
    logger.info(f'Total valid chunks: {total_valid:,}')
    logger.info(f'Total with embeddings: {total_embedded:,}')

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
