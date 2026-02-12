"""
OCR existing extracted images to populate document text.

Processes single-image documents first for quick wins, then handles multi-page docs.
Uses parallel processing for improved performance.
Now uses PostgreSQL for safe concurrent access from multiple machines.
"""
import re
import os
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger
import pytesseract
from PIL import Image
import psycopg2
from psycopg2.extras import execute_batch

# Configure Tesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# PostgreSQL connection
PG_CONN = {
    'host': 'localhost',
    'database': 'epstein_documents',
    'user': 'epstein_user',
    'password': 'epstein_secure_pw_2024'
}

# Settings
BATCH_SIZE = 100
LOG_INTERVAL = 100
MAX_IMAGES_PER_DOC = 50
NUM_WORKERS = 8

# Tesseract config
TESSERACT_CONFIG = '--oem 1 --psm 3'


def get_connection():
    """Get a new PostgreSQL connection."""
    return psycopg2.connect(**PG_CONN)


def extract_page_order(filename):
    """Extract page and image number from filename for sorting."""
    match = re.search(r'_p(\d+)_img(\d+)', filename)
    if match:
        return (int(match.group(1)), int(match.group(2)))
    return (0, 0)


def ocr_image(image_path):
    """OCR a single image and return the text."""
    try:
        path = Path(image_path)
        if not path.exists():
            return None
        img = Image.open(path)
        if img.mode not in ('L', 'RGB'):
            img = img.convert('RGB')
        text = pytesseract.image_to_string(img, config=TESSERACT_CONFIG)
        return text.strip() if text else None
    except Exception:
        return None


def ocr_single_doc(args):
    """Worker function to OCR a single-image document. Returns (doc_id, text)."""
    doc_id, efta_number, file_path = args
    text = ocr_image(file_path)
    return (doc_id, text)


def ocr_multi_doc(args):
    """Worker function to OCR a multi-image document. Returns (doc_id, full_text, page_count)."""
    doc_id, efta_number, images = args

    # Sort images by page order
    sorted_images = sorted(images, key=lambda x: extract_page_order(x[1]))

    text_parts = []
    for file_path, file_name in sorted_images:
        text = ocr_image(file_path)
        if text:
            text_parts.append(text)

    if text_parts:
        full_text = '\n\n'.join(text_parts)
        return (doc_id, full_text, len(sorted_images))

    return (doc_id, None, len(sorted_images))


def get_single_image_docs(conn, limit):
    """Get and claim documents with exactly 1 image (fastest to process)."""
    cursor = conn.cursor()
    # Use FOR UPDATE SKIP LOCKED to atomically claim documents
    cursor.execute('''
        WITH candidates AS (
            SELECT d.document_id
            FROM documents d
            WHERE d.extraction_status = 'partial'
            AND (d.full_text IS NULL OR LENGTH(d.full_text) < 100)
            AND d.document_id IN (
                SELECT source_document_id
                FROM media_files
                WHERE media_type = 'image'
                GROUP BY source_document_id
                HAVING COUNT(*) = 1
            )
            LIMIT %s
            FOR UPDATE SKIP LOCKED
        )
        UPDATE documents d
        SET extraction_status = 'processing'
        FROM candidates c
        WHERE d.document_id = c.document_id
        RETURNING d.document_id, d.efta_number
    ''', (limit,))
    claimed_docs = cursor.fetchall()
    conn.commit()

    if not claimed_docs:
        return []

    # Get file paths for claimed documents
    doc_ids = [d[0] for d in claimed_docs]
    cursor.execute('''
        SELECT d.document_id, d.efta_number, m.file_path
        FROM documents d
        JOIN media_files m ON d.document_id = m.source_document_id
        WHERE d.document_id = ANY(%s)
        AND m.media_type = 'image'
    ''', (doc_ids,))
    return cursor.fetchall()


def process_single_image_docs_parallel(conn, docs, executor):
    """Process documents with single images using parallel OCR."""
    success = 0
    no_text = 0

    # Submit all OCR tasks
    futures = {executor.submit(ocr_single_doc, doc): doc[0] for doc in docs}

    # Collect results
    results = []
    for future in as_completed(futures):
        doc_id, text = future.result()
        results.append((doc_id, text))

    # Batch update database with retry logic
    max_retries = 3
    for attempt in range(max_retries):
        try:
            cursor = conn.cursor()
            for doc_id, text in results:
                if text and len(text) > 50:
                    cursor.execute('''
                        UPDATE documents
                        SET full_text = %s,
                            extraction_status = 'completed',
                            page_count = 1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE document_id = %s
                    ''', (text, doc_id))
                    success += 1
                else:
                    cursor.execute('''
                        UPDATE documents
                        SET extraction_status = 'completed',
                            page_count = 1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE document_id = %s
                    ''', (doc_id,))
                    no_text += 1
            conn.commit()
            break
        except psycopg2.errors.DeadlockDetected:
            conn.rollback()
            if attempt < max_retries - 1:
                logger.warning(f"Deadlock detected, retry {attempt + 1}/{max_retries}")
                time.sleep(0.5 * (attempt + 1))
            else:
                raise

    return success, no_text


def get_multi_image_docs_with_images(conn, limit, max_images):
    """Get and claim documents with their images for parallel processing."""
    cursor = conn.cursor()
    # Claim documents atomically
    cursor.execute('''
        WITH candidates AS (
            SELECT d.document_id
            FROM documents d
            WHERE d.extraction_status = 'partial'
            AND (d.full_text IS NULL OR LENGTH(d.full_text) < 100)
            AND d.document_id IN (
                SELECT source_document_id
                FROM media_files
                WHERE media_type = 'image'
                GROUP BY source_document_id
                HAVING COUNT(*) > 1 AND COUNT(*) <= %s
            )
            LIMIT %s
            FOR UPDATE SKIP LOCKED
        )
        UPDATE documents d
        SET extraction_status = 'processing'
        FROM candidates c
        WHERE d.document_id = c.document_id
        RETURNING d.document_id, d.efta_number
    ''', (max_images, limit))
    claimed_docs = cursor.fetchall()
    conn.commit()

    if not claimed_docs:
        return []

    result = []
    for doc_id, efta_number in claimed_docs:
        cursor.execute('''
            SELECT file_path, file_name
            FROM media_files
            WHERE source_document_id = %s
            AND media_type = 'image'
        ''', (doc_id,))
        images = cursor.fetchall()
        if images:
            result.append((doc_id, efta_number, images))

    return result


def process_multi_image_docs_parallel(conn, docs_with_images, executor):
    """Process multi-image documents using parallel OCR."""
    success = 0
    no_text = 0

    # Submit all OCR tasks
    futures = {executor.submit(ocr_multi_doc, doc): doc[0] for doc in docs_with_images}

    # Collect results
    results = []
    for future in as_completed(futures):
        doc_id, full_text, page_count = future.result()
        results.append((doc_id, full_text, page_count))

    # Batch update database with retry logic
    max_retries = 3
    for attempt in range(max_retries):
        try:
            cursor = conn.cursor()
            for doc_id, full_text, page_count in results:
                if full_text and len(full_text) > 50:
                    cursor.execute('''
                        UPDATE documents
                        SET full_text = %s,
                            extraction_status = 'completed',
                            page_count = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE document_id = %s
                    ''', (full_text, page_count, doc_id))
                    success += 1
                else:
                    cursor.execute('''
                        UPDATE documents
                        SET extraction_status = 'completed',
                            page_count = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE document_id = %s
                    ''', (page_count, doc_id))
                    no_text += 1
            conn.commit()
            break
        except psycopg2.errors.DeadlockDetected:
            conn.rollback()
            if attempt < max_retries - 1:
                logger.warning(f"Deadlock detected, retry {attempt + 1}/{max_retries}")
                time.sleep(0.5 * (attempt + 1))
            else:
                raise

    return success, no_text


def main():
    logger.info("Starting OCR of existing images (PostgreSQL)...")
    logger.info(f"Max images per doc: {MAX_IMAGES_PER_DOC}")
    logger.info(f"Parallel threads: {NUM_WORKERS}")

    # Check tesseract
    try:
        version = pytesseract.get_tesseract_version()
        logger.info(f"Tesseract version: {version}")
    except Exception as e:
        logger.error(f"Tesseract not available: {e}")
        sys.exit(1)

    # Connect to PostgreSQL
    try:
        conn = get_connection()
        cursor = conn.cursor()
        logger.info("Connected to PostgreSQL")
    except Exception as e:
        logger.error(f"PostgreSQL connection failed: {e}")
        sys.exit(1)

    # Phase 1: Single-image documents (fast)
    logger.info("Phase 1: Processing single-image documents...")

    cursor.execute('''
        SELECT COUNT(*) FROM documents d
        WHERE d.extraction_status IN ('partial', 'processing')
        AND d.document_id IN (
            SELECT source_document_id
            FROM media_files
            WHERE media_type = 'image'
            GROUP BY source_document_id
            HAVING COUNT(*) = 1
        )
    ''')
    single_count = cursor.fetchone()[0]
    logger.info(f"Found {single_count:,} single-image documents")

    start_time = time.time()
    processed = 0
    total_success = 0
    total_no_text = 0

    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        while True:
            docs = get_single_image_docs(conn, BATCH_SIZE)
            if not docs:
                break

            success, no_text = process_single_image_docs_parallel(conn, docs, executor)

            total_success += success
            total_no_text += no_text
            processed += len(docs)

            if processed % LOG_INTERVAL == 0 or processed >= single_count:
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                remaining = single_count - processed
                eta_min = (remaining / rate / 60) if rate > 0 else 0

                logger.info(
                    f"Single-image: {processed:,}/{single_count:,} ({100*processed/single_count:.1f}%) | "
                    f"Success: {total_success:,} | Rate: {rate:.1f}/sec | ETA: {eta_min:.0f}min"
                )

    logger.info(f"Phase 1 complete: {processed:,} docs, {total_success:,} with text")

    # Phase 2: Multi-image documents
    logger.info(f"Phase 2: Processing multi-image documents (up to {MAX_IMAGES_PER_DOC} images)...")

    cursor.execute('''
        SELECT COUNT(*) FROM documents d
        WHERE d.extraction_status IN ('partial', 'processing')
        AND d.document_id IN (
            SELECT source_document_id
            FROM media_files
            WHERE media_type = 'image'
            GROUP BY source_document_id
            HAVING COUNT(*) > 1 AND COUNT(*) <= %s
        )
    ''', (MAX_IMAGES_PER_DOC,))
    multi_count = cursor.fetchone()[0]
    logger.info(f"Found {multi_count:,} multi-image documents")

    start_time = time.time()
    processed = 0
    phase2_success = 0
    phase2_no_text = 0

    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        while True:
            docs_with_images = get_multi_image_docs_with_images(conn, BATCH_SIZE, MAX_IMAGES_PER_DOC)
            if not docs_with_images:
                break

            success, no_text = process_multi_image_docs_parallel(conn, docs_with_images, executor)

            phase2_success += success
            phase2_no_text += no_text
            processed += len(docs_with_images)

            if processed % LOG_INTERVAL == 0 or processed >= multi_count:
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                remaining = multi_count - processed
                eta_min = (remaining / rate / 60) if rate > 0 else 0

                logger.info(
                    f"Multi-image: {processed:,}/{multi_count:,} ({100*processed/multi_count:.1f}%) | "
                    f"Success: {phase2_success:,} | Rate: {rate:.1f}/sec | ETA: {eta_min:.0f}min"
                )

    conn.close()

    total_time = time.time() - start_time
    logger.info(f"\n=== OCR Complete ===")
    logger.info(f"Single-image docs: {single_count:,} ({total_success:,} with text)")
    logger.info(f"Multi-image docs: {multi_count:,} ({phase2_success:,} with text)")
    logger.info(f"Total with text: {total_success + phase2_success:,}")
    logger.info(f"Time: {total_time/60:.1f} minutes")


if __name__ == "__main__":
    main()
