"""
Extraction job handler - downloads PDFs from R2 and extracts text.

Handles the 'extract_text' job type. Each job downloads a single PDF from
Cloudflare R2, runs the extraction pipeline (pymupdf → pdfplumber → OCR),
updates the documents table, then cleans up.

Example payload:
    {
        "action": "extract_text",
        "document_id": 12345,
        "r2_key": "DataSet_10/0051/EFTA01383430.pdf",
        "db_url": "host=... dbname=..."   # injected by worker
    }
"""

import os
import time
import tempfile
import logging
from pathlib import Path

import boto3
import psycopg2

# Add parent paths so extractors/services resolve
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from extractors.pdf_extractor import PDFExtractor
from services.job_handlers.general_handler import JobResult

logger = logging.getLogger(__name__)

# ── R2 credentials (same as download_to_r2.py / extract_photos_to_r2.py) ──
R2_ENDPOINT = "https://f8370fa3403bc68c2a46a3ad87be970d.r2.cloudflarestorage.com"
R2_ACCESS_KEY = "ae0a78c0037d7ac13df823d2e085777c"
R2_SECRET_KEY = "6aed78ea947b634aa80d78b3d7d976493c1926501eecd77e4faa0691bc85faa2"
R2_BUCKET = "epsteinfiles"

# Module-level reusable instances
_s3_client = None
_extractor = None


def _get_s3_client():
    """Lazily create and reuse a boto3 S3 client for R2."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=R2_ENDPOINT,
            aws_access_key_id=R2_ACCESS_KEY,
            aws_secret_access_key=R2_SECRET_KEY,
            region_name="auto",
        )
    return _s3_client


def _get_extractor():
    global _extractor
    if _extractor is None:
        _extractor = PDFExtractor()
    return _extractor


def handle_extraction_job(payload: dict) -> JobResult:
    """
    Download a PDF from R2, extract text, and update the documents table.

    Args:
        payload: Must contain 'document_id', 'r2_key', and 'db_url'.

    Returns:
        JobResult with extraction metadata on success.
    """
    document_id = payload.get('document_id')
    r2_key = payload.get('r2_key')
    db_url = payload.get('db_url')

    if not document_id or not r2_key:
        return JobResult(
            success=False,
            error="Missing required fields: document_id and r2_key",
        )
    if not db_url:
        return JobResult(
            success=False,
            error="Missing db_url in payload (should be injected by worker)",
        )

    start_time = time.time()
    tmp_path = None

    try:
        # 1. Download PDF from R2 to a temp file
        s3 = _get_s3_client()
        suffix = os.path.splitext(r2_key)[1] or '.pdf'
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix=f"extract_{document_id}_")
        os.close(tmp_fd)

        logger.info(f"[{document_id}] Downloading {r2_key}")
        s3.download_file(R2_BUCKET, r2_key, tmp_path)

        file_size = os.path.getsize(tmp_path)
        if file_size == 0:
            _update_document(db_url, document_id, extraction_status='no_text',
                             error_note='Empty file in R2')
            return JobResult(
                success=True,
                output=f"Document {document_id}: empty file (0 bytes)",
                result_data={'document_id': document_id, 'extraction_status': 'no_text',
                             'reason': 'empty_file'},
            )

        # 2. Extract text using PDFExtractor (pymupdf → pdfplumber → OCR)
        logger.info(f"[{document_id}] Extracting text ({file_size:,} bytes)")
        extractor = _get_extractor()
        result = extractor.extract(tmp_path)

        if result is None:
            _update_document(db_url, document_id, extraction_status='failed')
            return JobResult(
                success=False,
                error=f"PDFExtractor returned None for document {document_id}",
            )

        full_text = result.get('full_text', '') or ''
        page_count = result.get('page_count', 0)
        is_redacted = result.get('is_redacted', False)
        redaction_level = result.get('redaction_level', 'none')
        extraction_method = result.get('extraction_method', 'unknown')
        document_type = result.get('document_type')

        # 3. Determine extraction status
        text_length = len(full_text.strip())
        if text_length > 0:
            extraction_status = 'completed'
        else:
            extraction_status = 'no_text'

        # 4. Update the documents table
        _update_document(
            db_url, document_id,
            full_text=full_text if text_length > 0 else None,
            extraction_status=extraction_status,
            page_count=page_count,
            is_redacted=is_redacted,
            redaction_level=redaction_level,
            document_type=document_type,
        )

        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            f"[{document_id}] {extraction_status} — "
            f"{text_length:,} chars, {page_count} pages, "
            f"method={extraction_method}, {duration_ms}ms"
        )

        return JobResult(
            success=True,
            output=f"Document {document_id}: {extraction_status} "
                   f"({text_length:,} chars, {page_count} pages, {extraction_method})",
            result_data={
                'document_id': document_id,
                'page_count': page_count,
                'text_length': text_length,
                'extraction_method': extraction_method,
                'extraction_status': extraction_status,
                'is_redacted': is_redacted,
                'redaction_level': redaction_level,
                'duration_ms': duration_ms,
            },
        )

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        error_msg = f"{type(e).__name__}: {e}"
        logger.error(f"[{document_id}] Extraction failed: {error_msg}")

        # Mark as failed in DB so we don't re-submit
        try:
            _update_document(db_url, document_id, extraction_status='failed')
        except Exception:
            pass

        return JobResult(
            success=False,
            error=error_msg,
            result_data={'document_id': document_id, 'duration_ms': duration_ms},
        )

    finally:
        # 6. Clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _update_document(
    db_url: str,
    document_id: int,
    full_text: str = None,
    extraction_status: str = None,
    page_count: int = None,
    is_redacted: bool = None,
    redaction_level: str = None,
    document_type: str = None,
):
    """Update document columns in PostgreSQL."""
    sets = []
    params = []

    if full_text is not None:
        sets.append("full_text = %s")
        params.append(full_text)
    if extraction_status is not None:
        sets.append("extraction_status = %s")
        params.append(extraction_status)
    if page_count is not None:
        sets.append("page_count = %s")
        params.append(page_count)
    if is_redacted is not None:
        sets.append("is_redacted = %s")
        params.append(is_redacted)
    if redaction_level is not None:
        sets.append("redaction_level = %s")
        params.append(redaction_level)
    if document_type is not None:
        sets.append("document_type = %s")
        params.append(document_type)

    sets.append("updated_at = NOW()")
    params.append(document_id)

    sql = f"UPDATE documents SET {', '.join(sets)} WHERE document_id = %s"

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
