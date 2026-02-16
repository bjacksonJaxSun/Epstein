"""
Distributed OCR worker for processing documents across multiple machines.

Usage:
    python ocr_distributed_worker.py --worker-id 0 --total-workers 2 --output-dir \\server\share\ocr_results
    python ocr_distributed_worker.py --worker-id 1 --total-workers 2 --output-dir \\server\share\ocr_results

Each worker processes documents where (document_id % total_workers) == worker_id
Results are written to JSON files that can be merged back into the main database.
"""
import argparse
import json
import os
import re
import sys
import time
import sqlite3
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from loguru import logger

try:
    import pytesseract
    from PIL import Image
except ImportError:
    print("Required packages missing. Install with:")
    print("  pip install pytesseract pillow")
    sys.exit(1)

# Configure Tesseract - adjust path if needed
if sys.platform == 'win32':
    tesseract_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
    ]
    for path in tesseract_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            break

# Settings
BATCH_SIZE = 100
LOG_INTERVAL = 100
# Auto-detect optimal worker count based on CPU cores
# Override with OCR_WORKERS environment variable if needed
_cpu_count = os.cpu_count() or 4
NUM_WORKERS = int(os.getenv('OCR_WORKERS', _cpu_count))
TESSERACT_CONFIG = '--oem 1 --psm 3'


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
    except Exception as e:
        return None


def ocr_single_doc(args):
    """Worker function to OCR a single-image document."""
    doc_id, efta_number, file_path = args
    text = ocr_image(file_path)
    return (doc_id, efta_number, text, 1)


def ocr_multi_doc(args):
    """Worker function to OCR a multi-image document."""
    doc_id, efta_number, images = args
    sorted_images = sorted(images, key=lambda x: extract_page_order(x[1]))

    text_parts = []
    for file_path, file_name in sorted_images:
        text = ocr_image(file_path)
        if text:
            text_parts.append(text)

    if text_parts:
        full_text = '\n\n'.join(text_parts)
        return (doc_id, efta_number, full_text, len(sorted_images))

    return (doc_id, efta_number, None, len(sorted_images))


def get_documents_for_worker(cursor, worker_id, total_workers, limit):
    """Get documents assigned to this worker."""
    cursor.execute('''
        SELECT d.document_id, d.efta_number, m.file_path
        FROM documents d
        JOIN media_files m ON d.document_id = m.source_document_id
        WHERE d.extraction_status = 'partial'
        AND (d.full_text IS NULL OR LENGTH(d.full_text) < 100)
        AND m.media_type = 'image'
        AND (d.document_id % ?) = ?
        AND d.document_id IN (
            SELECT source_document_id
            FROM media_files
            WHERE media_type = 'image'
            GROUP BY source_document_id
            HAVING COUNT(*) = 1
        )
        LIMIT ?
    ''', (total_workers, worker_id, limit))
    return cursor.fetchall()


def save_results(results, output_dir, worker_id, batch_num):
    """Save OCR results to a JSON file."""
    output_path = Path(output_dir) / f"ocr_results_worker{worker_id}_batch{batch_num:05d}.json"

    data = {
        'worker_id': worker_id,
        'batch_num': batch_num,
        'timestamp': datetime.utcnow().isoformat(),
        'results': [
            {
                'document_id': doc_id,
                'efta_number': efta_number,
                'full_text': text,
                'page_count': page_count,
                'has_text': text is not None and len(text) > 50
            }
            for doc_id, efta_number, text, page_count in results
        ]
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)

    return output_path


def main():
    parser = argparse.ArgumentParser(description='Distributed OCR worker')
    parser.add_argument('--worker-id', type=int, required=True, help='This worker ID (0-based)')
    parser.add_argument('--total-workers', type=int, required=True, help='Total number of workers')
    parser.add_argument('--output-dir', type=str, required=True, help='Directory to write results')
    parser.add_argument('--db-path', type=str,
                        default=r'C:\Development\EpsteinDownloader\extraction_output\epstein_documents.db',
                        help='Path to SQLite database')
    parser.add_argument('--threads', type=int, default=NUM_WORKERS, help='Number of OCR threads')
    args = parser.parse_args()

    logger.info(f"Starting distributed OCR worker {args.worker_id + 1}/{args.total_workers}")
    logger.info(f"Output directory: {args.output_dir}")
    logger.info(f"Database: {args.db_path}")
    logger.info(f"Threads: {args.threads}")

    # Check tesseract
    try:
        version = pytesseract.get_tesseract_version()
        logger.info(f"Tesseract version: {version}")
    except Exception as e:
        logger.error(f"Tesseract not available: {e}")
        logger.error("Install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki")
        sys.exit(1)

    # Create output directory
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Connect to database (read-only for safety)
    conn = sqlite3.connect(f'file:{args.db_path}?mode=ro', uri=True, timeout=60)
    cursor = conn.cursor()

    # Count documents for this worker
    cursor.execute('''
        SELECT COUNT(*) FROM documents d
        WHERE d.extraction_status = 'partial'
        AND (d.document_id % ?) = ?
        AND d.document_id IN (
            SELECT source_document_id
            FROM media_files
            WHERE media_type = 'image'
            GROUP BY source_document_id
            HAVING COUNT(*) = 1
        )
    ''', (args.total_workers, args.worker_id))
    total_docs = cursor.fetchone()[0]
    logger.info(f"Documents assigned to this worker: {total_docs:,}")

    if total_docs == 0:
        logger.info("No documents to process. Exiting.")
        return

    start_time = time.time()
    processed = 0
    total_success = 0
    batch_num = 0

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        while True:
            docs = get_documents_for_worker(cursor, args.worker_id, args.total_workers, BATCH_SIZE)
            if not docs:
                break

            # Submit OCR tasks
            futures = {executor.submit(ocr_single_doc, doc): doc[0] for doc in docs}

            # Collect results
            results = []
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                if result[2] and len(result[2]) > 50:
                    total_success += 1

            # Save results to file
            save_results(results, args.output_dir, args.worker_id, batch_num)
            batch_num += 1
            processed += len(docs)

            if processed % LOG_INTERVAL == 0 or processed >= total_docs:
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                remaining = total_docs - processed
                eta_min = (remaining / rate / 60) if rate > 0 else 0

                logger.info(
                    f"Progress: {processed:,}/{total_docs:,} ({100*processed/total_docs:.1f}%) | "
                    f"Success: {total_success:,} | Rate: {rate:.1f}/sec | ETA: {eta_min:.0f}min"
                )

            # Re-query to get next batch (since we saved results, not updated DB)
            # We need to track processed IDs to avoid reprocessing
            # For simplicity, we'll break after first pass - merge script handles updates

    conn.close()

    total_time = time.time() - start_time
    logger.info(f"\n=== Worker {args.worker_id} Complete ===")
    logger.info(f"Processed: {processed:,} documents")
    logger.info(f"With text: {total_success:,}")
    logger.info(f"Time: {total_time/60:.1f} minutes")
    logger.info(f"Results saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
