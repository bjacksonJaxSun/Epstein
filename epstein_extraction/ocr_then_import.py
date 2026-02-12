"""
OCR completion monitor + Dataset 10 auto-import.
Monitors OCR progress and starts Dataset 10 import when complete.

Usage:
    python ocr_then_import.py
"""
import os
import sys
import time
import subprocess
from pathlib import Path
from loguru import logger

try:
    import psycopg2
except ImportError:
    print("Install: pip install psycopg2-binary")
    sys.exit(1)

# Configuration
PG_CONN = {
    'host': 'localhost',
    'database': 'epstein_documents',
    'user': 'epstein_user',
    'password': 'epstein_secure_pw_2024'
}

DATASET_10_ZIP = Path(r"D:\DataSet 10.zip")
IMPORT_SCRIPT = Path(__file__).parent / "load_dataset_incremental.py"
CHECK_INTERVAL = 30  # seconds


def get_ocr_status():
    """Check OCR processing status."""
    conn = psycopg2.connect(**PG_CONN)
    cur = conn.cursor()

    # Documents still being processed
    cur.execute("""
        SELECT COUNT(*) FROM documents
        WHERE extraction_status IN ('partial', 'processing')
    """)
    pending = cur.fetchone()[0]

    # Documents with text
    cur.execute("""
        SELECT COUNT(*) FROM documents
        WHERE full_text IS NOT NULL AND LENGTH(full_text) > 100
    """)
    with_text = cur.fetchone()[0]

    conn.close()
    return pending, with_text


def is_ocr_running():
    """Check if OCR processes are still running."""
    # Check for Python processes running OCR scripts
    try:
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq python.exe'],
            capture_output=True, text=True
        )
        # Count python processes (excluding this one)
        lines = [l for l in result.stdout.split('\n') if 'python.exe' in l.lower()]
        return len(lines) > 1  # More than just this script
    except Exception:
        return False


def start_import():
    """Start the Dataset 10 import."""
    logger.info("=" * 60)
    logger.info("STARTING DATASET 10 IMPORT")
    logger.info("=" * 60)
    logger.info(f"Zip file: {DATASET_10_ZIP}")
    logger.info(f"Import script: {IMPORT_SCRIPT}")

    if not DATASET_10_ZIP.exists():
        logger.error(f"Dataset 10 zip not found: {DATASET_10_ZIP}")
        return False

    if not IMPORT_SCRIPT.exists():
        logger.error(f"Import script not found: {IMPORT_SCRIPT}")
        return False

    # Run the import script
    os.chdir(IMPORT_SCRIPT.parent)
    subprocess.run([
        sys.executable,
        str(IMPORT_SCRIPT),
        str(DATASET_10_ZIP)
    ])

    return True


def main():
    logger.info("=" * 60)
    logger.info("OCR COMPLETION MONITOR + AUTO-IMPORT")
    logger.info("=" * 60)
    logger.info(f"Checking every {CHECK_INTERVAL} seconds")
    logger.info(f"Will start import of: {DATASET_10_ZIP}")

    # Initial status
    pending, with_text = get_ocr_status()
    logger.info(f"Initial status: {pending} pending, {with_text} with text")

    if pending == 0:
        logger.info("No OCR work pending - starting import immediately!")
        start_import()
        return

    # Monitor loop
    last_pending = pending
    stable_count = 0

    while True:
        time.sleep(CHECK_INTERVAL)

        pending, with_text = get_ocr_status()
        ocr_running = is_ocr_running()

        logger.info(
            f"Status: {pending} pending, {with_text} with text, "
            f"OCR processes: {'running' if ocr_running else 'stopped'}"
        )

        # Check if OCR is complete
        if pending == 0:
            logger.info("OCR complete - all documents processed!")
            break

        # Check if OCR is stalled (no progress and no processes)
        if pending == last_pending:
            stable_count += 1
            if stable_count >= 3 and not ocr_running:
                logger.warning(f"OCR appears stalled ({pending} still pending but no processes)")
                logger.info("Proceeding with import anyway...")
                break
        else:
            stable_count = 0
            last_pending = pending

    # Start the import
    start_import()


if __name__ == "__main__":
    main()
