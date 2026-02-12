"""
Parallel-safe dataset loader - multiple instances can run simultaneously.
Uses a coordination table with FOR UPDATE SKIP LOCKED to prevent duplicate work.
"""

import os
import sys
import zipfile
import shutil
import tempfile
import hashlib
import socket
from pathlib import Path
from datetime import datetime

import fitz  # PyMuPDF
from sqlalchemy import text

from config import SessionLocal, engine, logger, OUTPUT_DIR
from extractors import PDFExtractor
from models import Document, MediaFile

BATCH_SIZE = 50  # Claim 50 files at a time
WORKER_ID = f"{socket.gethostname()}_{os.getpid()}"

# Output directory for extracted images
IMAGES_OUTPUT_DIR = OUTPUT_DIR / "extracted_images"
IMAGES_OUTPUT_DIR.mkdir(exist_ok=True)


def create_pending_imports_table():
    """Create the coordination table if it doesn't exist."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS pending_imports (
                id SERIAL PRIMARY KEY,
                filename TEXT UNIQUE NOT NULL,
                efta_number TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                claimed_by TEXT,
                claimed_at TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pending_imports_status ON pending_imports(status)"))
        conn.commit()
    logger.info("Pending imports table ready")


def populate_pending_imports_from_dir(dir_path: str):
    """Populate the pending_imports table with files from a directory."""
    logger.info(f"Scanning directory for PDFs: {dir_path}")

    pdf_entries = []
    base_dir = Path(dir_path)
    for pdf_file in base_dir.rglob('*.pdf'):
        # Store relative path from the parent of the provided directory
        # so it matches zip-style paths like VOL00010/IMAGES/...
        rel_path = pdf_file.relative_to(base_dir.parent).as_posix()
        pdf_entries.append(rel_path)
    # Also check for .PDF extension
    for pdf_file in base_dir.rglob('*.PDF'):
        rel_path = pdf_file.relative_to(base_dir.parent).as_posix()
        if rel_path not in pdf_entries:
            pdf_entries.append(rel_path)

    logger.info(f"Found {len(pdf_entries)} PDF files in directory")
    _insert_pending_imports(pdf_entries)


def populate_pending_imports(zip_path: str):
    """Populate the pending_imports table with files from the zip."""
    logger.info("Scanning zip file for PDFs...")

    pdf_entries = []
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for info in zf.infolist():
            if info.filename.lower().endswith('.pdf') and not info.is_dir():
                pdf_entries.append(info.filename)

    logger.info(f"Found {len(pdf_entries)} PDF files in archive")
    _insert_pending_imports(pdf_entries)


def _insert_pending_imports(pdf_entries: list):
    """Insert PDF entries into the pending_imports table."""

    # Get existing documents and pending imports
    with engine.connect() as conn:
        # Get already imported EFTA numbers
        result = conn.execute(text("SELECT efta_number FROM documents"))
        existing_eftas = {row[0] for row in result}

        # Get already queued files
        result = conn.execute(text("SELECT filename FROM pending_imports"))
        queued_files = {row[0] for row in result}

    logger.info(f"Already in database: {len(existing_eftas)} documents")
    logger.info(f"Already queued: {len(queued_files)} files")

    # Build list of new files to insert
    to_insert = []
    for entry in pdf_entries:
        if entry in queued_files:
            continue

        filename = os.path.basename(entry)
        efta = filename.replace('.pdf', '').replace('.PDF', '')

        if efta in existing_eftas:
            continue

        to_insert.append({"filename": entry, "efta": efta})

    logger.info(f"Files to insert: {len(to_insert)}")

    # Batch insert for much better performance
    BATCH_INSERT_SIZE = 5000
    new_count = 0
    with engine.connect() as conn:
        for i in range(0, len(to_insert), BATCH_INSERT_SIZE):
            batch = to_insert[i:i + BATCH_INSERT_SIZE]
            try:
                conn.execute(
                    text("""
                        INSERT INTO pending_imports (filename, efta_number, status)
                        VALUES (:filename, :efta, 'pending')
                        ON CONFLICT (filename) DO NOTHING
                    """),
                    batch
                )
                new_count += len(batch)
                if i % 50000 == 0:
                    logger.info(f"  Inserted {new_count} files...")
            except Exception as e:
                logger.warning(f"Batch insert error: {e}")
        conn.commit()

    logger.info(f"Added {new_count} new files to queue")

    # Get queue status
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT status, COUNT(*) FROM pending_imports GROUP BY status
        """))
        for row in result:
            logger.info(f"  {row[0]}: {row[1]}")


def claim_batch():
    """Claim a batch of files to process using FOR UPDATE SKIP LOCKED."""
    with engine.connect() as conn:
        # Claim files atomically
        result = conn.execute(text("""
            UPDATE pending_imports
            SET status = 'processing', claimed_by = :worker, claimed_at = NOW()
            WHERE id IN (
                SELECT id FROM pending_imports
                WHERE status = 'pending'
                ORDER BY id
                LIMIT :batch_size
                FOR UPDATE SKIP LOCKED
            )
            RETURNING id, filename, efta_number
        """), {"worker": WORKER_ID, "batch_size": BATCH_SIZE})

        claimed = [(row[0], row[1], row[2]) for row in result]
        conn.commit()

    return claimed


def mark_completed(file_id: int):
    """Mark a file as completed."""
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE pending_imports
            SET status = 'completed', completed_at = NOW()
            WHERE id = :id
        """), {"id": file_id})
        conn.commit()


def mark_error(file_id: int, error_msg: str):
    """Mark a file as errored."""
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE pending_imports
            SET status = 'error', error_message = :error, completed_at = NOW()
            WHERE id = :id
        """), {"id": file_id, "error": str(error_msg)[:500]})
        conn.commit()


def extract_images_from_pdf(session, document_id: int, efta_number: str, pdf_path: str) -> int:
    """Extract images from a PDF and catalog them in the database."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return 0

    doc_output_dir = IMAGES_OUTPUT_DIR / efta_number
    doc_output_dir.mkdir(exist_ok=True)
    images_extracted = 0

    try:
        doc = fitz.open(pdf_path)

        for page_num in range(doc.page_count):
            page = doc[page_num]
            image_list = page.get_images(full=True)

            for img_index, img in enumerate(image_list):
                try:
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    width = base_image.get("width", 0)
                    height = base_image.get("height", 0)

                    if width < 50 or height < 50:
                        continue

                    checksum = hashlib.sha256(image_bytes).hexdigest()
                    existing = session.query(MediaFile).filter(MediaFile.checksum == checksum).first()
                    if existing:
                        continue

                    image_filename = f"{efta_number}_p{page_num + 1}_img{img_index + 1}.{image_ext}"
                    image_path = doc_output_dir / image_filename

                    with open(image_path, "wb") as img_file:
                        img_file.write(image_bytes)

                    orientation = 'landscape' if width > height else ('portrait' if height > width else 'square')

                    media_file = MediaFile(
                        file_path=str(image_path.absolute()),
                        file_name=image_filename,
                        media_type='image',
                        file_format=image_ext,
                        file_size_bytes=len(image_bytes),
                        checksum=checksum,
                        width_pixels=width,
                        height_pixels=height,
                        orientation=orientation,
                        source_document_id=document_id,
                        original_filename=image_filename,
                        caption=f"Extracted from {efta_number}, page {page_num + 1}",
                    )
                    session.add(media_file)
                    images_extracted += 1

                except Exception as e:
                    logger.debug(f"Error extracting image {img_index} from page {page_num}: {e}")

        doc.close()

        # Render pages for scanned docs with no embedded images
        if images_extracted == 0 and doc.page_count <= 20:
            images_extracted = render_pages_as_images(session, document_id, efta_number, pdf_path, doc_output_dir)

    except Exception as e:
        logger.debug(f"Image extraction failed for {efta_number}: {e}")

    return images_extracted


def render_pages_as_images(session, document_id: int, efta_number: str, pdf_path: Path, output_dir: Path) -> int:
    """Render PDF pages as images when no embedded images are found."""
    try:
        doc = fitz.open(pdf_path)
        images_extracted = 0

        for page_num in range(min(doc.page_count, 10)):
            page = doc[page_num]
            mat = fitz.Matrix(150/72, 150/72)
            pix = page.get_pixmap(matrix=mat)

            image_filename = f"{efta_number}_page{page_num + 1}.png"
            image_path = output_dir / image_filename
            pix.save(str(image_path))

            with open(image_path, 'rb') as f:
                checksum = hashlib.sha256(f.read()).hexdigest()

            existing = session.query(MediaFile).filter(MediaFile.checksum == checksum).first()
            if existing:
                os.remove(image_path)
                continue

            width, height = pix.width, pix.height
            orientation = 'landscape' if width > height else ('portrait' if height > width else 'square')

            media_file = MediaFile(
                file_path=str(image_path.absolute()),
                file_name=image_filename,
                media_type='image',
                file_format='png',
                file_size_bytes=image_path.stat().st_size,
                checksum=checksum,
                width_pixels=width,
                height_pixels=height,
                orientation=orientation,
                source_document_id=document_id,
                original_filename=image_filename,
                caption=f"Extracted from {efta_number}, page {page_num + 1}",
            )
            session.add(media_file)
            images_extracted += 1

        doc.close()
        return images_extracted

    except Exception as e:
        logger.debug(f"Page rendering failed for {efta_number}: {e}")
        return 0


def process_file_from_dir(base_dir: str, filename: str, efta_number: str,
                          session, extractor: PDFExtractor, no_images: bool = False) -> tuple:
    """Process a single PDF file from an unzipped directory. Returns (success, images_count, error)."""
    try:
        # Construct full path: base_dir is parent of VOL dir, filename is relative like VOL00010/IMAGES/...
        filepath = os.path.join(base_dir, filename.replace('/', os.sep))
        if not os.path.exists(filepath):
            return False, 0, f"File not found: {filepath}"

        # Extract PDF content
        result = extractor.extract(filepath)

        if result:
            doc = Document(
                efta_number=efta_number,
                file_path=filepath,
                full_text=result.get('text', ''),
                page_count=result.get('page_count'),
                file_size_bytes=os.path.getsize(filepath),
                extraction_status='completed' if result.get('text') else 'partial',
            )
        else:
            doc = Document(
                efta_number=efta_number,
                file_path=filepath,
                full_text=None,
                page_count=None,
                file_size_bytes=os.path.getsize(filepath) if os.path.exists(filepath) else 0,
                extraction_status='failed',
            )

        session.add(doc)
        session.flush()

        # Extract images (skip if --no-images)
        img_count = 0
        if not no_images:
            img_count = extract_images_from_pdf(session, doc.document_id, efta_number, filepath)

            if img_count > 0 and doc.extraction_status == 'failed':
                doc.extraction_status = 'partial'

        session.commit()
        return True, img_count, None

    except Exception as e:
        session.rollback()
        return False, 0, str(e)


def process_file(zip_path: str, temp_dir: str, filename: str, efta_number: str,
                 session, extractor: PDFExtractor, no_images: bool = False) -> tuple:
    """Process a single PDF file from zip. Returns (success, images_count)."""
    try:
        # Extract from zip
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extract(filename, temp_dir)

        # Find the extracted file
        filepath = os.path.join(temp_dir, filename)
        if not os.path.exists(filepath):
            return False, 0, "File not extracted"

        # Extract PDF content
        result = extractor.extract(filepath)

        if result:
            doc = Document(
                efta_number=efta_number,
                file_path=filepath,
                full_text=result.get('text', ''),
                page_count=result.get('page_count'),
                file_size_bytes=os.path.getsize(filepath),
                extraction_status='completed' if result.get('text') else 'partial',
            )
        else:
            doc = Document(
                efta_number=efta_number,
                file_path=filepath,
                full_text=None,
                page_count=None,
                file_size_bytes=os.path.getsize(filepath) if os.path.exists(filepath) else 0,
                extraction_status='failed',
            )

        session.add(doc)
        session.flush()

        # Extract images (skip if --no-images)
        img_count = 0
        if not no_images:
            img_count = extract_images_from_pdf(session, doc.document_id, efta_number, filepath)

            if img_count > 0 and doc.extraction_status == 'failed':
                doc.extraction_status = 'partial'

        session.commit()

        # Clean up extracted file
        try:
            os.remove(filepath)
            # Try to remove parent dirs if empty
            parent = os.path.dirname(filepath)
            while parent != temp_dir:
                if os.path.isdir(parent) and not os.listdir(parent):
                    os.rmdir(parent)
                    parent = os.path.dirname(parent)
                else:
                    break
        except:
            pass

        return True, img_count, None

    except Exception as e:
        session.rollback()
        return False, 0, str(e)


def get_queue_status():
    """Get current queue status."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT status, COUNT(*) FROM pending_imports GROUP BY status ORDER BY status
        """))
        return {row[0]: row[1] for row in result}


def main():
    args = sys.argv[1:]

    if not args:
        print("Usage: python load_dataset_parallel.py <zip_file_path> [--no-images]")
        print("       python load_dataset_parallel.py --dir <directory_path> [--no-images]")
        print("       python load_dataset_parallel.py --status")
        sys.exit(1)

    if '--status' in args:
        create_pending_imports_table()
        status = get_queue_status()
        print("\nQueue Status:")
        for s, count in status.items():
            print(f"  {s}: {count}")
        total = sum(status.values())
        completed = status.get('completed', 0)
        print(f"\nProgress: {completed}/{total} ({100*completed/total:.1f}%)" if total > 0 else "\nNo files in queue")
        sys.exit(0)

    # Parse flags
    no_images = '--no-images' in args
    if no_images:
        args.remove('--no-images')

    # Determine mode: directory or zip
    use_dir = False
    if '--dir' in args:
        dir_idx = args.index('--dir')
        if dir_idx + 1 >= len(args):
            print("Error: --dir requires a directory path")
            sys.exit(1)
        source_path = args[dir_idx + 1]
        use_dir = True
        if not os.path.isdir(source_path):
            print(f"Error: Directory not found: {source_path}")
            sys.exit(1)
    else:
        source_path = args[0]
        if not os.path.exists(source_path):
            print(f"Error: Zip file not found: {source_path}")
            sys.exit(1)

    print(f"Worker ID: {WORKER_ID}")
    print(f"Mode: {'Directory' if use_dir else 'Zip'}")
    print(f"No images: {no_images}")
    print(f"Source: {source_path}")
    print(f"Images will be saved to: {IMAGES_OUTPUT_DIR}")

    # Setup
    create_pending_imports_table()
    if use_dir:
        populate_pending_imports_from_dir(source_path)
        # Base dir is the parent of the provided directory (e.g., D:\Personal\Epstein)
        base_dir = str(Path(source_path).parent)
    else:
        populate_pending_imports(source_path)

    # Show initial status
    status = get_queue_status()
    pending = status.get('pending', 0)
    print(f"\nPending files: {pending}")

    if pending == 0:
        print("No pending files to process!")
        sys.exit(0)

    # Create temp directory (only needed for zip mode)
    temp_dir = None
    if not use_dir:
        temp_dir = tempfile.mkdtemp(prefix=f'parallel_import_{WORKER_ID}_')
        print(f"Using temp directory: {temp_dir}")

    extractor = PDFExtractor()
    session = SessionLocal()

    total_processed = 0
    total_images = 0
    total_errors = 0

    try:
        while True:
            # Claim a batch
            claimed = claim_batch()

            if not claimed:
                # Check if there's still work being done by others
                status = get_queue_status()
                processing = status.get('processing', 0)
                pending = status.get('pending', 0)

                if pending == 0 and processing == 0:
                    print("\nAll files processed!")
                    break
                elif pending == 0:
                    print(f"\nWaiting for {processing} files being processed by other workers...")
                    import time
                    time.sleep(5)
                    continue
                else:
                    # Should have gotten files, try again
                    continue

            print(f"\n{'='*60}")
            print(f"Claimed {len(claimed)} files (Total processed: {total_processed})")
            print(f"{'='*60}")

            for file_id, filename, efta_number in claimed:
                if use_dir:
                    success, img_count, error = process_file_from_dir(
                        base_dir, filename, efta_number, session, extractor, no_images=no_images
                    )
                else:
                    success, img_count, error = process_file(
                        source_path, temp_dir, filename, efta_number, session, extractor, no_images=no_images
                    )

                if success:
                    mark_completed(file_id)
                    total_processed += 1
                    total_images += img_count

                    if total_processed % 10 == 0:
                        status = get_queue_status()
                        pending = status.get('pending', 0)
                        completed = status.get('completed', 0)
                        print(f"  Processed: {total_processed} | Images: {total_images} | "
                              f"Queue: {pending} pending, {completed} completed")
                else:
                    mark_error(file_id, error)
                    total_errors += 1
                    logger.warning(f"Failed: {efta_number} - {error}")

        print(f"\n{'='*60}")
        print(f"WORKER {WORKER_ID} COMPLETE")
        print(f"Processed: {total_processed}")
        print(f"Images: {total_images}")
        print(f"Errors: {total_errors}")
        print(f"{'='*60}")

        # Final status
        status = get_queue_status()
        print("\nFinal Queue Status:")
        for s, count in status.items():
            print(f"  {s}: {count}")

    finally:
        session.close()
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"Cleaned up temp directory")


if __name__ == '__main__':
    main()
