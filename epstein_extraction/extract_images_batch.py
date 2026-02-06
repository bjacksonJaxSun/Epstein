"""
Extract images from existing documents that don't have images yet.
Processes in batches to avoid memory issues.
"""

import sys
import os
import hashlib
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import fitz  # PyMuPDF
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from config import SessionLocal, OUTPUT_DIR, logger
from models import Document, MediaFile


def commit_with_retry(session, max_retries=5):
    """Commit with retry logic for database locks."""
    for attempt in range(max_retries):
        try:
            session.commit()
            return True
        except OperationalError as e:
            if "database is locked" in str(e):
                wait_time = (attempt + 1) * 2  # Exponential backoff
                print(f"Database locked, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})...")
                session.rollback()
                time.sleep(wait_time)
            else:
                raise
    return False

# Output directory for extracted images
IMAGES_OUTPUT_DIR = OUTPUT_DIR / "extracted_images"
IMAGES_OUTPUT_DIR.mkdir(exist_ok=True)

BATCH_SIZE = 100


def get_documents_without_images(session, limit: int = None):
    """Get documents that don't have any associated media files."""
    query = text("""
        SELECT d.document_id, d.efta_number, d.file_path
        FROM documents d
        LEFT JOIN media_files m ON d.document_id = m.source_document_id
        WHERE m.media_file_id IS NULL
        AND d.file_path IS NOT NULL
        ORDER BY d.document_id
    """ + (f" LIMIT {limit}" if limit else ""))

    result = session.execute(query)
    return [(row[0], row[1], row[2]) for row in result]


def extract_images_from_pdf(session, document_id: int, efta_number: str, pdf_path: str) -> int:
    """Extract images from a PDF and catalog them in the database."""
    pdf_path = Path(pdf_path)

    # Handle path remapping
    if not pdf_path.exists():
        # Try remapping from old JaxSun path
        remapped = str(pdf_path).replace(
            r"C:\Development\JaxSun.Ideas\tools\EpsteinDownloader\\",
            r"C:\Development\EpsteinDownloader\\"
        )
        if os.path.exists(remapped):
            pdf_path = Path(remapped)
        else:
            return 0

    if not pdf_path.exists():
        return 0

    # Create output directory for this document's images
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

                    # Skip very small images (likely icons or artifacts)
                    if width < 50 or height < 50:
                        continue

                    # Calculate checksum
                    checksum = hashlib.sha256(image_bytes).hexdigest()

                    # Check if already in database
                    existing = session.query(MediaFile).filter(MediaFile.checksum == checksum).first()
                    if existing:
                        continue

                    # Save image
                    image_filename = f"{efta_number}_p{page_num + 1}_img{img_index + 1}.{image_ext}"
                    image_path = doc_output_dir / image_filename

                    with open(image_path, "wb") as img_file:
                        img_file.write(image_bytes)

                    # Determine orientation
                    if width > height:
                        orientation = 'landscape'
                    elif height > width:
                        orientation = 'portrait'
                    else:
                        orientation = 'square'

                    # Create media file record
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
                    pass  # Skip problematic images silently

        doc.close()

    except Exception as e:
        logger.debug(f"Image extraction failed for {efta_number}: {e}")

    return images_extracted


def main():
    session = SessionLocal()

    print("Finding documents without images...")
    docs = get_documents_without_images(session)
    print(f"Found {len(docs):,} documents to process")

    if not docs:
        print("No documents need image extraction!")
        session.close()
        return

    total_images = 0
    processed = 0
    docs_with_images = 0

    print(f"\nExtracting images from {len(docs):,} documents...")
    print(f"Images will be saved to: {IMAGES_OUTPUT_DIR}")
    print()

    for i, (doc_id, efta, path) in enumerate(docs):
        if i % 100 == 0 and i > 0:
            if not commit_with_retry(session):
                print("Failed to commit after retries, skipping...")
                continue
            print(f"Progress: {i:,}/{len(docs):,} ({100*i/len(docs):.1f}%) - {total_images:,} images from {docs_with_images:,} docs")

        img_count = extract_images_from_pdf(session, doc_id, efta, path)
        total_images += img_count
        processed += 1
        if img_count > 0:
            docs_with_images += 1

    commit_with_retry(session)
    session.close()

    print(f"\n{'='*60}")
    print(f"COMPLETE")
    print(f"Documents processed: {processed:,}")
    print(f"Documents with images: {docs_with_images:,}")
    print(f"Total images extracted: {total_images:,}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
