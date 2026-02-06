"""
Incremental dataset loader - extracts and processes PDFs in batches to save disk space.
Extracts a batch, loads to database, extracts images, deletes extracted files, repeats.
"""

import os
import sys
import zipfile
import shutil
import tempfile
import hashlib
from pathlib import Path

import fitz  # PyMuPDF

from config import SessionLocal, logger, OUTPUT_DIR
from extractors import PDFExtractor
from models import Document, MediaFile

BATCH_SIZE = 500  # Process 500 PDFs at a time

# Output directory for extracted images
IMAGES_OUTPUT_DIR = OUTPUT_DIR / "extracted_images"
IMAGES_OUTPUT_DIR.mkdir(exist_ok=True)


def get_existing_efta_numbers(session):
    """Get all EFTA numbers already in the database."""
    result = session.query(Document.efta_number).all()
    return {r[0] for r in result if r[0]}


def extract_batch(zip_path: str, pdf_names: list, extract_dir: str):
    """Extract a batch of PDFs from the zip file."""
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for name in pdf_names:
            try:
                zf.extract(name, extract_dir)
            except Exception as e:
                logger.warning(f"Failed to extract {name}: {e}")


def extract_images_from_pdf(session, document_id: int, efta_number: str, pdf_path: str) -> int:
    """
    Extract images from a PDF and catalog them in the database.

    Returns:
        Number of images extracted
    """
    pdf_path = Path(pdf_path)

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
                    logger.debug(f"Error extracting image {img_index} from page {page_num}: {e}")

        doc.close()

        # If no embedded images, render pages as images for scanned docs
        if images_extracted == 0 and doc.page_count <= 20:  # Only for smaller docs
            images_extracted = render_pages_as_images(session, document_id, efta_number, pdf_path, doc_output_dir)

    except Exception as e:
        logger.debug(f"Image extraction failed for {efta_number}: {e}")

    return images_extracted


def render_pages_as_images(session, document_id: int, efta_number: str, pdf_path: Path, output_dir: Path) -> int:
    """Render PDF pages as images when no embedded images are found."""
    try:
        doc = fitz.open(pdf_path)
        images_extracted = 0

        for page_num in range(min(doc.page_count, 10)):  # Limit to first 10 pages
            page = doc[page_num]

            # Render page at 150 DPI
            mat = fitz.Matrix(150/72, 150/72)
            pix = page.get_pixmap(matrix=mat)

            image_filename = f"{efta_number}_page{page_num + 1}.png"
            image_path = output_dir / image_filename

            pix.save(str(image_path))

            # Calculate checksum
            with open(image_path, 'rb') as f:
                checksum = hashlib.sha256(f.read()).hexdigest()

            # Check if already in database
            existing = session.query(MediaFile).filter(MediaFile.checksum == checksum).first()
            if existing:
                os.remove(image_path)
                continue

            width, height = pix.width, pix.height
            if width > height:
                orientation = 'landscape'
            elif height > width:
                orientation = 'portrait'
            else:
                orientation = 'square'

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
                caption=f"Page {page_num + 1} of {efta_number}",
            )

            session.add(media_file)
            images_extracted += 1

        doc.close()
        return images_extracted

    except Exception as e:
        logger.debug(f"Page rendering failed for {efta_number}: {e}")
        return 0


def process_batch(extract_dir: str, session, extractor: PDFExtractor, extract_images: bool = True):
    """Process all PDFs in the extract directory."""
    processed = 0
    total_images = 0

    for root, dirs, files in os.walk(extract_dir):
        for filename in files:
            if not filename.lower().endswith('.pdf'):
                continue

            filepath = os.path.join(root, filename)
            efta_number = filename.replace('.pdf', '').replace('.PDF', '')

            try:
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
                    session.add(doc)
                    session.flush()  # Get the document ID

                    # Extract images
                    if extract_images:
                        img_count = extract_images_from_pdf(session, doc.document_id, efta_number, filepath)
                        total_images += img_count

                    processed += 1

                    if processed % 50 == 0:
                        session.commit()
                        logger.info(f"Committed {processed} documents, {total_images} images in this batch")

            except Exception as e:
                logger.error(f"Error processing {filename}: {e}")
                continue

    session.commit()
    return processed, total_images


def main():
    if len(sys.argv) < 2:
        print("Usage: python load_dataset_incremental.py <zip_file_path> [--no-images]")
        sys.exit(1)

    zip_path = sys.argv[1]
    extract_images = '--no-images' not in sys.argv

    if not os.path.exists(zip_path):
        print(f"Error: Zip file not found: {zip_path}")
        sys.exit(1)

    print(f"Processing: {zip_path}")
    print(f"Image extraction: {'enabled' if extract_images else 'disabled'}")

    # Get list of PDFs in the zip
    print("Scanning zip file for PDFs...")
    pdf_entries = []
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for info in zf.infolist():
            if info.filename.lower().endswith('.pdf') and not info.is_dir():
                pdf_entries.append(info.filename)

    print(f"Found {len(pdf_entries)} PDF files in archive")

    # Get existing EFTA numbers
    session = SessionLocal()
    existing_eftas = get_existing_efta_numbers(session)
    print(f"Already in database: {len(existing_eftas)} documents")

    # Filter out already-loaded PDFs
    new_pdfs = []
    for entry in pdf_entries:
        filename = os.path.basename(entry)
        efta = filename.replace('.pdf', '').replace('.PDF', '')
        if efta not in existing_eftas:
            new_pdfs.append(entry)

    print(f"New PDFs to load: {len(new_pdfs)}")

    if not new_pdfs:
        print("No new documents to load!")
        session.close()
        return

    # Create temp directory for extraction
    temp_dir = tempfile.mkdtemp(prefix='dataset10_batch_')
    print(f"Using temp directory: {temp_dir}")
    print(f"Images will be saved to: {IMAGES_OUTPUT_DIR}")

    extractor = PDFExtractor()
    total_processed = 0
    total_images = 0

    try:
        # Process in batches
        for i in range(0, len(new_pdfs), BATCH_SIZE):
            batch = new_pdfs[i:i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            total_batches = (len(new_pdfs) + BATCH_SIZE - 1) // BATCH_SIZE

            print(f"\n{'='*60}")
            print(f"BATCH {batch_num}/{total_batches}: Processing {len(batch)} PDFs")
            print(f"Progress: {total_processed}/{len(new_pdfs)} ({100*total_processed/len(new_pdfs):.1f}%)")
            print(f"Total images so far: {total_images}")
            print(f"{'='*60}")

            # Clear temp directory
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)

            # Extract batch
            print(f"Extracting {len(batch)} PDFs...")
            extract_batch(zip_path, batch, temp_dir)

            # Process batch
            print("Processing extracted PDFs...")
            processed, images = process_batch(temp_dir, session, extractor, extract_images)
            total_processed += processed
            total_images += images
            print(f"Processed {processed} documents, {images} images in this batch")

            # Add to existing set to avoid reprocessing
            for entry in batch:
                filename = os.path.basename(entry)
                efta = filename.replace('.pdf', '').replace('.PDF', '')
                existing_eftas.add(efta)

        print(f"\n{'='*60}")
        print(f"COMPLETE: Processed {total_processed} new documents")
        print(f"Total images extracted: {total_images}")
        print(f"{'='*60}")

    finally:
        # Cleanup
        session.close()
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"Cleaned up temp directory")


if __name__ == '__main__':
    main()
