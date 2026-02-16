"""
OCR worker for remote machine - connects to PostgreSQL over the network.

Run from any machine with Tesseract installed:
    python ocr_worker_remote.py

PostgreSQL handles concurrent access safely - no more corruption issues!
"""
import os
import re
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger

try:
    import pytesseract
    from PIL import Image
    import psycopg2
except ImportError:
    print("Install required packages: pip install pytesseract pillow loguru psycopg2-binary")
    sys.exit(1)

# Tesseract path (on remote machine)
if sys.platform == 'win32':
    for path in [r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                 r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe']:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            break

# PostgreSQL connection - UPDATE THIS IP TO THE DATABASE SERVER
PG_CONN = {
    'host': 'BOBBYHOMEEP',  # Change to IP address if hostname doesn't resolve
    'database': 'epstein_documents',
    'user': 'epstein_user',
    'password': 'epstein_secure_pw_2024'
}

# Path configuration - for accessing files over network share
SHARE_BASE = r'\\BOBBYHOMEEP\EpsteinDownloader'
LOCAL_BASE = r'C:\Development\EpsteinDownloader'

# Settings
BATCH_SIZE = 100
# Auto-detect optimal worker count based on CPU cores
# Override with OCR_WORKERS environment variable if needed
_cpu_count = os.cpu_count() or 4
NUM_WORKERS = int(os.getenv('OCR_WORKERS', _cpu_count))
TESSERACT_CONFIG = '--oem 1 --psm 3'


def translate_path(local_path):
    """Convert local path to UNC path for network access."""
    if local_path and local_path.startswith(LOCAL_BASE):
        return local_path.replace(LOCAL_BASE, SHARE_BASE)
    return local_path


def get_connection():
    """Get a new PostgreSQL connection."""
    return psycopg2.connect(**PG_CONN)


def ocr_image(image_path):
    """OCR a single image and return the text."""
    try:
        # Translate path for network access
        unc_path = translate_path(image_path)
        path = Path(unc_path)
        if not path.exists():
            logger.debug(f"Image not found: {unc_path}")
            return None
        img = Image.open(path)
        if img.mode not in ('L', 'RGB'):
            img = img.convert('RGB')
        text = pytesseract.image_to_string(img, config=TESSERACT_CONFIG)
        return text.strip() if text else None
    except Exception as e:
        logger.debug(f"OCR error: {e}")
        return None


def ocr_doc(args):
    """OCR a single document."""
    doc_id, efta_number, file_path = args
    text = ocr_image(file_path)
    return (doc_id, text)


def extract_page_order(filename):
    """Extract page and image number from filename for sorting."""
    match = re.search(r'_p(\d+)_img(\d+)', filename)
    if match:
        return (int(match.group(1)), int(match.group(2)))
    return (0, 0)


def get_dynamic_progress(cursor, range_clause="HAVING COUNT(*) = 1"):
    """Get dynamic progress counts from database for accurate percentage calculation."""
    # Count documents with OCR text (completed successfully)
    cursor.execute('''
        SELECT COUNT(*) FROM documents
        WHERE full_text IS NOT NULL AND LENGTH(full_text) > 100
    ''')
    completed_with_text = cursor.fetchone()[0]

    # Count documents still needing OCR (matching the range)
    cursor.execute(f'''
        SELECT COUNT(*) FROM documents d
        WHERE (d.extraction_status IN ('partial', 'extracted', 'processing'))
        AND (d.full_text IS NULL OR LENGTH(d.full_text) < 100)
        AND d.document_id IN (
            SELECT source_document_id FROM media_files
            WHERE media_type = 'image'
            GROUP BY source_document_id {range_clause}
        )
    ''')
    remaining = cursor.fetchone()[0]

    return completed_with_text, remaining


def ocr_multi_doc(args):
    """OCR a multi-image document. Returns (doc_id, full_text, page_count)."""
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


def main():
    logger.info("=" * 60)
    logger.info("OCR Remote Worker (PostgreSQL)")
    logger.info("=" * 60)
    logger.info(f"Database: {PG_CONN['host']}")
    logger.info(f"Network share: {SHARE_BASE}")
    logger.info(f"Threads: {NUM_WORKERS}")

    # Check Tesseract
    try:
        version = pytesseract.get_tesseract_version()
        logger.info(f"Tesseract version: {version}")
    except Exception as e:
        logger.error(f"Tesseract not available: {e}")
        logger.error("Install from: https://github.com/UB-Mannheim/tesseract/wiki")
        sys.exit(1)

    # Test share access
    if not os.path.exists(SHARE_BASE):
        logger.error(f"Cannot access share: {SHARE_BASE}")
        logger.error("Make sure the network share is accessible")
        sys.exit(1)
    logger.info(f"Share accessible: {SHARE_BASE}")

    # Connect to PostgreSQL
    try:
        conn = get_connection()
        cursor = conn.cursor()
        logger.info("PostgreSQL connected")
    except Exception as e:
        logger.error(f"PostgreSQL connection failed: {e}")
        logger.error(f"Check that PostgreSQL is accessible at {PG_CONN['host']}")
        sys.exit(1)

    # Count documents needing OCR
    cursor.execute('''
        SELECT COUNT(*) FROM documents d
        WHERE d.extraction_status IN ('partial', 'processing')
        AND d.document_id IN (
            SELECT source_document_id FROM media_files
            WHERE media_type = 'image'
            GROUP BY source_document_id HAVING COUNT(*) = 1
        )
    ''')
    total_docs = cursor.fetchone()[0]
    logger.info(f"Single-image documents needing OCR: {total_docs:,}")

    start_time = time.time()
    processed = 0
    success_count = 0

    # Phase 1: Single-image documents
    if total_docs > 0:
        logger.info("Phase 1: Processing single-image documents...")
        with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
            while True:
                # Claim documents atomically with FOR UPDATE SKIP LOCKED
                cursor.execute('''
                    WITH candidates AS (
                        SELECT d.document_id
                        FROM documents d
                        WHERE d.extraction_status = 'partial'
                        AND (d.full_text IS NULL OR LENGTH(d.full_text) < 100)
                        AND d.document_id IN (
                            SELECT source_document_id FROM media_files
                            WHERE media_type = 'image'
                            GROUP BY source_document_id HAVING COUNT(*) = 1
                        )
                        LIMIT %s
                        FOR UPDATE SKIP LOCKED
                    )
                    UPDATE documents d
                    SET extraction_status = 'processing'
                    FROM candidates c
                    WHERE d.document_id = c.document_id
                    RETURNING d.document_id, d.efta_number
                ''', (BATCH_SIZE,))
                claimed_docs = cursor.fetchall()
                conn.commit()

                if not claimed_docs:
                    break

                # Get file paths for claimed documents
                doc_ids = [d[0] for d in claimed_docs]
                cursor.execute('''
                    SELECT d.document_id, d.efta_number, m.file_path
                    FROM documents d
                    JOIN media_files m ON d.document_id = m.source_document_id
                    WHERE d.document_id = ANY(%s)
                    AND m.media_type = 'image'
                ''', (doc_ids,))
                docs = cursor.fetchall()

                if not docs:
                    break

                # Process batch in parallel
                futures = {executor.submit(ocr_doc, doc): doc[0] for doc in docs}
                results = []
                for future in as_completed(futures):
                    results.append(future.result())

                # Update database with retry logic
                max_retries = 3
                for attempt in range(max_retries):
                    try:
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
                                success_count += 1
                            else:
                                cursor.execute('''
                                    UPDATE documents
                                    SET extraction_status = 'completed',
                                        page_count = 1,
                                        updated_at = CURRENT_TIMESTAMP
                                    WHERE document_id = %s
                                ''', (doc_id,))
                        conn.commit()
                        break
                    except Exception as e:
                        conn.rollback()
                        if 'deadlock' in str(e).lower() and attempt < max_retries - 1:
                            logger.warning(f"Deadlock detected, retry {attempt + 1}/{max_retries}")
                            time.sleep(0.5 * (attempt + 1))
                        else:
                            raise

                processed += len(docs)

                # Progress report with dynamic counts
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0

                # Get dynamic counts for accurate progress
                completed_with_text, remaining = get_dynamic_progress(cursor, "HAVING COUNT(*) = 1")
                total_work = completed_with_text + remaining
                progress_pct = (100 * completed_with_text / total_work) if total_work > 0 else 100
                eta_min = (remaining / rate / 60) if rate > 0 else 0

                logger.info(
                    f"Progress: {remaining:,} remaining ({progress_pct:.1f}% complete) | "
                    f"Success: {success_count:,} | Rate: {rate:.1f}/sec | ETA: {eta_min:.0f}min"
                )

    logger.info(f"Phase 1 complete: {processed:,} docs, {success_count:,} with text")

    # Phase 2: Multi-image documents
    logger.info("=" * 60)
    logger.info("Phase 2: Processing multi-image documents...")

    cursor.execute('''
        SELECT COUNT(*) FROM documents d
        WHERE d.extraction_status IN ('partial', 'processing')
        AND d.document_id IN (
            SELECT source_document_id FROM media_files
            WHERE media_type = 'image'
            GROUP BY source_document_id HAVING COUNT(*) > 1 AND COUNT(*) <= 50
        )
    ''')
    multi_count = cursor.fetchone()[0]
    logger.info(f"Found {multi_count:,} multi-image documents")

    start_time = time.time()
    phase2_processed = 0
    phase2_success = 0
    MAX_IMAGES = 50

    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        while True:
            # Claim multi-image documents
            cursor.execute('''
                WITH candidates AS (
                    SELECT d.document_id
                    FROM documents d
                    WHERE d.extraction_status = 'partial'
                    AND (d.full_text IS NULL OR LENGTH(d.full_text) < 100)
                    AND d.document_id IN (
                        SELECT source_document_id FROM media_files
                        WHERE media_type = 'image'
                        GROUP BY source_document_id HAVING COUNT(*) > 1 AND COUNT(*) <= %s
                    )
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE documents d
                SET extraction_status = 'processing'
                FROM candidates c
                WHERE d.document_id = c.document_id
                RETURNING d.document_id, d.efta_number
            ''', (MAX_IMAGES, BATCH_SIZE))
            claimed_docs = cursor.fetchall()
            conn.commit()

            if not claimed_docs:
                break

            # Get all images for claimed documents
            docs_with_images = []
            for doc_id, efta_number in claimed_docs:
                cursor.execute('''
                    SELECT file_path, file_name
                    FROM media_files
                    WHERE source_document_id = %s
                    AND media_type = 'image'
                ''', (doc_id,))
                images = cursor.fetchall()
                if images:
                    docs_with_images.append((doc_id, efta_number, images))

            if not docs_with_images:
                break

            # Process batch in parallel
            futures = {executor.submit(ocr_multi_doc, doc): doc[0] for doc in docs_with_images}
            results = []
            for future in as_completed(futures):
                results.append(future.result())

            # Update database with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
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
                            phase2_success += 1
                        else:
                            cursor.execute('''
                                UPDATE documents
                                SET extraction_status = 'completed',
                                    page_count = %s,
                                    updated_at = CURRENT_TIMESTAMP
                                WHERE document_id = %s
                            ''', (page_count, doc_id))
                    conn.commit()
                    break
                except Exception as e:
                    conn.rollback()
                    if 'deadlock' in str(e).lower() and attempt < max_retries - 1:
                        logger.warning(f"Deadlock detected, retry {attempt + 1}/{max_retries}")
                        time.sleep(0.5 * (attempt + 1))
                    else:
                        raise

            phase2_processed += len(docs_with_images)

            # Progress report with dynamic counts
            elapsed = time.time() - start_time
            rate = phase2_processed / elapsed if elapsed > 0 else 0

            # Get dynamic counts for accurate progress
            completed_with_text, remaining = get_dynamic_progress(
                cursor, f"HAVING COUNT(*) > 1 AND COUNT(*) <= {MAX_IMAGES}"
            )
            total_work = completed_with_text + remaining
            progress_pct = (100 * completed_with_text / total_work) if total_work > 0 else 100
            eta_min = (remaining / rate / 60) if rate > 0 else 0

            logger.info(
                f"Multi-image: {remaining:,} remaining ({progress_pct:.1f}% complete) | "
                f"Success: {phase2_success:,} | Rate: {rate:.1f}/sec | ETA: {eta_min:.0f}min"
            )

    conn.close()

    total_time = time.time() - start_time
    logger.info("=" * 60)
    logger.info("OCR Worker Complete")
    logger.info("=" * 60)
    logger.info(f"Phase 1: {processed:,} docs, {success_count:,} with text")
    logger.info(f"Phase 2: {phase2_processed:,} docs, {phase2_success:,} with text")
    logger.info(f"Total with text: {success_count + phase2_success:,}")
    logger.info(f"Time: {total_time/60:.1f} minutes")


if __name__ == "__main__":
    main()
