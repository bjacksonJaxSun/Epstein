"""
OCR ALL documents - REMOTE MACHINE VERSION
Connects to PostgreSQL over the network and accesses files via share.

Run on machine 2:
    python ocr_all_documents_remote.py

PostgreSQL handles concurrent access safely with FOR UPDATE SKIP LOCKED.
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

# Tesseract path
if sys.platform == 'win32':
    for path in [r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                 r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe']:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            break

# PostgreSQL connection - REMOTE
PG_CONN = {
    'host': 'BOBBYHOMEEP',  # Database server hostname
    'database': 'epstein_documents',
    'user': 'epstein_user',
    'password': 'epstein_secure_pw_2024'
}

# Path translation for network access
SHARE_BASE = r'\\BOBBYHOMEEP\EpsteinDownloader'
LOCAL_BASE = r'C:\Development\EpsteinDownloader'

# Settings
BATCH_SIZE = 50  # Documents to claim at a time
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
        path = Path(translate_path(image_path))
        if not path.exists():
            return None
        img = Image.open(path)
        if img.mode not in ('L', 'RGB'):
            img = img.convert('RGB')
        text = pytesseract.image_to_string(img, config=TESSERACT_CONFIG)
        return text.strip() if text else None
    except Exception as e:
        logger.debug(f"OCR error: {e}")
        return None


def extract_page_order(filename):
    """Extract page and image number from filename for sorting."""
    match = re.search(r'_p(\d+)_img(\d+)', filename)
    if match:
        return (int(match.group(1)), int(match.group(2)))
    return (0, 0)


def ocr_single_doc(args):
    """OCR a single-image document."""
    doc_id, efta_number, file_path = args
    text = ocr_image(file_path)
    return (doc_id, text, 1)


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


def update_database(conn, results):
    """Update database with OCR results, with retry logic."""
    cursor = conn.cursor()
    max_retries = 3
    success_count = 0

    for attempt in range(max_retries):
        try:
            for doc_id, text, page_count in results:
                if text and len(text) > 50:
                    cursor.execute('''
                        UPDATE documents
                        SET full_text = %s,
                            extraction_status = 'completed',
                            page_count = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE document_id = %s
                    ''', (text, page_count, doc_id))
                    success_count += 1
                else:
                    cursor.execute('''
                        UPDATE documents
                        SET extraction_status = 'completed',
                            page_count = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE document_id = %s
                    ''', (page_count, doc_id))
            conn.commit()
            return success_count
        except Exception as e:
            conn.rollback()
            if 'deadlock' in str(e).lower() and attempt < max_retries - 1:
                logger.warning(f"Deadlock detected, retry {attempt + 1}/{max_retries}")
                time.sleep(0.5 * (attempt + 1))
            else:
                raise
    return 0


def process_single_image_docs(conn, executor):
    """Phase 1: Process all single-image documents."""
    cursor = conn.cursor()

    # Count total
    cursor.execute('''
        SELECT COUNT(*) FROM documents d
        WHERE (d.extraction_status = 'partial' OR d.extraction_status = 'extracted')
        AND (d.full_text IS NULL OR LENGTH(d.full_text) < 100)
        AND d.document_id IN (
            SELECT source_document_id FROM media_files
            WHERE media_type = 'image'
            GROUP BY source_document_id HAVING COUNT(*) = 1
        )
    ''')
    total_docs = cursor.fetchone()[0]
    logger.info(f"Single-image documents needing OCR: {total_docs:,}")

    if total_docs == 0:
        return 0, 0

    start_time = time.time()
    processed = 0
    success_count = 0

    while True:
        # Claim documents atomically
        cursor.execute('''
            WITH candidates AS (
                SELECT d.document_id
                FROM documents d
                WHERE (d.extraction_status = 'partial' OR d.extraction_status = 'extracted')
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

        # Get file paths
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
        futures = {executor.submit(ocr_single_doc, doc): doc[0] for doc in docs}
        results = [future.result() for future in as_completed(futures)]

        # Update database
        batch_success = update_database(conn, results)
        success_count += batch_success
        processed += len(docs)

        # Progress report
        elapsed = time.time() - start_time
        rate = processed / elapsed if elapsed > 0 else 0
        remaining = total_docs - processed
        eta_min = (remaining / rate / 60) if rate > 0 else 0

        logger.info(
            f"Single-image: {processed:,}/{total_docs:,} ({100*processed/total_docs:.1f}%) | "
            f"Success: {success_count:,} | Rate: {rate:.1f}/sec | ETA: {eta_min:.0f}min"
        )

    return processed, success_count


def process_multi_image_docs(conn, executor, min_images=2, max_images=None):
    """Phase 2+: Process multi-image documents within range."""
    cursor = conn.cursor()

    # Build query for image count range
    if max_images:
        range_clause = f"HAVING COUNT(*) >= {min_images} AND COUNT(*) <= {max_images}"
        range_name = f"{min_images}-{max_images} images"
    else:
        range_clause = f"HAVING COUNT(*) >= {min_images}"
        range_name = f"{min_images}+ images"

    # Count total
    cursor.execute(f'''
        SELECT COUNT(*) FROM documents d
        WHERE (d.extraction_status = 'partial' OR d.extraction_status = 'extracted')
        AND (d.full_text IS NULL OR LENGTH(d.full_text) < 100)
        AND d.document_id IN (
            SELECT source_document_id FROM media_files
            WHERE media_type = 'image'
            GROUP BY source_document_id {range_clause}
        )
    ''')
    total_docs = cursor.fetchone()[0]
    logger.info(f"Documents with {range_name} needing OCR: {total_docs:,}")

    if total_docs == 0:
        return 0, 0

    start_time = time.time()
    processed = 0
    success_count = 0

    while True:
        # Claim documents atomically
        cursor.execute(f'''
            WITH candidates AS (
                SELECT d.document_id
                FROM documents d
                WHERE (d.extraction_status = 'partial' OR d.extraction_status = 'extracted')
                AND (d.full_text IS NULL OR LENGTH(d.full_text) < 100)
                AND d.document_id IN (
                    SELECT source_document_id FROM media_files
                    WHERE media_type = 'image'
                    GROUP BY source_document_id {range_clause}
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

        # Process batch (large docs one at a time to avoid memory issues)
        results = []
        for doc in docs_with_images:
            result = ocr_multi_doc(doc)
            results.append(result)

        # Update database
        batch_success = update_database(conn, results)
        success_count += batch_success
        processed += len(docs_with_images)

        # Progress report
        elapsed = time.time() - start_time
        rate = processed / elapsed if elapsed > 0 else 0
        remaining = total_docs - processed
        eta_min = (remaining / rate / 60) if rate > 0 else 0

        logger.info(
            f"{range_name}: {processed:,}/{total_docs:,} ({100*processed/total_docs:.1f}%) | "
            f"Success: {success_count:,} | Rate: {rate:.1f}/sec | ETA: {eta_min:.0f}min"
        )

    return processed, success_count


def main():
    logger.info("=" * 70)
    logger.info("OCR ALL DOCUMENTS - REMOTE WORKER")
    logger.info("=" * 70)
    logger.info(f"Database: {PG_CONN['host']}")
    logger.info(f"Network share: {SHARE_BASE}")
    logger.info(f"Threads: {NUM_WORKERS}")

    # Check Tesseract
    try:
        version = pytesseract.get_tesseract_version()
        logger.info(f"Tesseract version: {version}")
    except Exception as e:
        logger.error(f"Tesseract not available: {e}")
        sys.exit(1)

    # Check share access
    if not os.path.exists(SHARE_BASE):
        logger.error(f"Cannot access share: {SHARE_BASE}")
        logger.error("Make sure the network share is accessible")
        sys.exit(1)
    logger.info(f"Share accessible: {SHARE_BASE}")

    # Connect to PostgreSQL
    try:
        conn = get_connection()
        logger.info("PostgreSQL connected")
    except Exception as e:
        logger.error(f"PostgreSQL connection failed: {e}")
        logger.error(f"Check that PostgreSQL is accessible at {PG_CONN['host']}")
        sys.exit(1)

    total_start = time.time()
    total_processed = 0
    total_success = 0

    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        # Phase 1: Single-image documents (fastest)
        logger.info("\n" + "=" * 70)
        logger.info("PHASE 1: Single-image documents")
        logger.info("=" * 70)
        p, s = process_single_image_docs(conn, executor)
        total_processed += p
        total_success += s

        # Phase 2: Small multi-image documents (2-10 images)
        logger.info("\n" + "=" * 70)
        logger.info("PHASE 2: Small multi-image documents (2-10 images)")
        logger.info("=" * 70)
        p, s = process_multi_image_docs(conn, executor, min_images=2, max_images=10)
        total_processed += p
        total_success += s

        # Phase 3: Medium multi-image documents (11-50 images)
        logger.info("\n" + "=" * 70)
        logger.info("PHASE 3: Medium multi-image documents (11-50 images)")
        logger.info("=" * 70)
        p, s = process_multi_image_docs(conn, executor, min_images=11, max_images=50)
        total_processed += p
        total_success += s

        # Phase 4: Large documents (51-100 images)
        logger.info("\n" + "=" * 70)
        logger.info("PHASE 4: Large documents (51-100 images)")
        logger.info("=" * 70)
        p, s = process_multi_image_docs(conn, executor, min_images=51, max_images=100)
        total_processed += p
        total_success += s

        # Phase 5: Very large documents (101-200 images)
        logger.info("\n" + "=" * 70)
        logger.info("PHASE 5: Very large documents (101-200 images)")
        logger.info("=" * 70)
        p, s = process_multi_image_docs(conn, executor, min_images=101, max_images=200)
        total_processed += p
        total_success += s

        # Phase 6: Massive documents (200+ images)
        logger.info("\n" + "=" * 70)
        logger.info("PHASE 6: Massive documents (200+ images)")
        logger.info("=" * 70)
        p, s = process_multi_image_docs(conn, executor, min_images=201, max_images=None)
        total_processed += p
        total_success += s

    conn.close()

    total_time = time.time() - total_start
    logger.info("\n" + "=" * 70)
    logger.info("OCR COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Total processed: {total_processed:,}")
    logger.info(f"Total with text: {total_success:,}")
    logger.info(f"Total time: {total_time/60:.1f} minutes")


if __name__ == "__main__":
    main()
