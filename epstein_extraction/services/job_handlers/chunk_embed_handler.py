"""
Chunk + embed job handler - splits document text into chunks and generates embeddings.

Handles the 'chunk_embed' job type. Each job fetches a single document's text,
splits it into token-based chunks, generates sentence-transformer embeddings,
and inserts into the document_chunks table.

Chunking parameters match Scripts/run_rag_complete_fixed.py for consistency
with the existing 881K chunks.

Example payload:
    {
        "action": "chunk_embed",
        "document_id": 12345,
        "db_url": "host=... dbname=..."   # injected by worker
    }
"""

import json
import logging
import os
import urllib.request

import psycopg2
from psycopg2.extras import execute_batch

from services.job_handlers.general_handler import JobResult

logger = logging.getLogger(__name__)

# Chunking parameters (must match run_rag_complete_fixed.py)
CHUNK_SIZE = 600       # tokens per chunk
CHUNK_OVERLAP = 100    # overlap tokens between chunks
MIN_CHUNK_SIZE = 30    # skip chunks smaller than this

def _get_embedding_url(db_url: str | None = None) -> str:
    """Resolve embedding server URL.

    Priority:
    1. EMBEDDING_SERVER_URL env var (explicit override)
    2. Auto-detect from db_url host — if the DB is on a remote host,
       the embedding server is assumed to be on the same host at port 5050
    3. Fallback to localhost:5050
    """
    env_url = os.environ.get("EMBEDDING_SERVER_URL")
    if env_url:
        return env_url
    if db_url:
        for part in db_url.split():
            if part.startswith("host="):
                host = part[5:].strip()
                if host and host not in ("localhost", "127.0.0.1", ""):
                    return f"http://{host}:5050"
    return "http://localhost:5050"

# Lazy singleton — loaded once per worker process
_encoding = None


def _get_encoding():
    """Lazily load tiktoken encoding."""
    global _encoding
    if _encoding is None:
        import tiktoken
        _encoding = tiktoken.get_encoding('cl100k_base')
    return _encoding


# ── Text processing functions (from run_rag_complete_fixed.py) ──

def count_tokens(text):
    if not text:
        return 0
    return len(_get_encoding().encode(text))


def chunk_text(text):
    if not text or not text.strip():
        return []

    encoding = _get_encoding()
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


def generate_embeddings(texts, embedding_url: str):
    if not texts:
        return []
    body = json.dumps({"texts": texts}).encode()
    req = urllib.request.Request(
        f"{embedding_url}/embed/batch",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())["embeddings"]


# ── Main handler ──

def handle_chunk_embed_job(payload: dict) -> JobResult:
    """
    Chunk a document's text and generate embeddings.

    Args:
        payload: Must contain 'document_id' and 'db_url'.

    Returns:
        JobResult with chunk count on success.
    """
    document_id = payload.get('document_id')
    db_url = payload.get('db_url')
    embedding_url = _get_embedding_url(db_url)

    if not document_id:
        return JobResult(success=False, error="Missing required field: document_id")
    if not db_url:
        return JobResult(success=False, error="Missing db_url in payload (should be injected by worker)")

    # Fail fast if dependencies are missing
    try:
        _get_encoding()
    except ImportError as e:
        return JobResult(success=False, error=f"Missing dependency: tiktoken ({e})")

    try:
        with psycopg2.connect(db_url) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                # Idempotency check — skip if chunks already exist
                cur.execute("SELECT COUNT(*) FROM document_chunks WHERE document_id = %s", (document_id,))
                existing = cur.fetchone()[0]
                if existing > 0:
                    return JobResult(
                        success=True,
                        output=f"Document {document_id}: already has {existing} chunks, skipped",
                        result_data={'document_id': document_id, 'chunk_count': existing, 'skipped': True},
                    )

                # Fetch document text
                cur.execute(
                    "SELECT full_text, video_transcript FROM documents WHERE document_id = %s",
                    (document_id,)
                )
                row = cur.fetchone()
                if not row:
                    return JobResult(
                        success=False,
                        error=f"Document {document_id} not found",
                    )

                full_text, video_transcript = row
                combined = combine_document_text(full_text, video_transcript)

                # No valid text — insert marker
                if not combined or len(combined.strip()) < 50:
                    cur.execute(
                        """INSERT INTO document_chunks
                           (document_id, chunk_index, chunk_text, chunk_tokens, start_char, end_char)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        (document_id, -1, '[NO_TEXT]', 0, 0, 0)
                    )
                    return JobResult(
                        success=True,
                        output=f"Document {document_id}: no valid text, inserted marker",
                        result_data={'document_id': document_id, 'chunk_count': 0, 'marker': 'NO_TEXT'},
                    )

                # Chunk the text
                chunks = chunk_text(combined)

                if not chunks:
                    cur.execute(
                        """INSERT INTO document_chunks
                           (document_id, chunk_index, chunk_text, chunk_tokens, start_char, end_char)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        (document_id, -1, '[NO_CHUNKS]', 0, 0, 0)
                    )
                    return JobResult(
                        success=True,
                        output=f"Document {document_id}: text too short for chunks, inserted marker",
                        result_data={'document_id': document_id, 'chunk_count': 0, 'marker': 'NO_CHUNKS'},
                    )

                # Generate embeddings for all chunks in one batch
                chunk_texts = [c['text'] for c in chunks]
                embeddings = generate_embeddings(chunk_texts, embedding_url)

                # Insert chunks with embeddings
                insert_data = []
                for idx, (c, emb) in enumerate(zip(chunks, embeddings)):
                    insert_data.append((
                        document_id, idx, c['text'], c['tokens'],
                        c['start_char'], c['end_char'], emb
                    ))

                execute_batch(cur, """
                    INSERT INTO document_chunks
                    (document_id, chunk_index, chunk_text, chunk_tokens, start_char, end_char, embedding_vector)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, insert_data)

                chunk_count = len(insert_data)
                logger.info(f"[{document_id}] Inserted {chunk_count} chunks with embeddings")

                return JobResult(
                    success=True,
                    output=f"Document {document_id}: {chunk_count} chunks created with embeddings",
                    result_data={'document_id': document_id, 'chunk_count': chunk_count},
                )

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        logger.error(f"[{document_id}] Chunk+embed failed: {error_msg}")
        return JobResult(
            success=False,
            error=error_msg,
            result_data={'document_id': document_id},
        )
