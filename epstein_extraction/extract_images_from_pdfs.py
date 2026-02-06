"""
Extract images from image-based PDFs and catalog them in the database.
"""
import sys
import os
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from config import SessionLocal, OUTPUT_DIR
from extractors import ImageExtractor
from models import Document, MediaFile
from loguru import logger


# Output directory for extracted images
IMAGES_OUTPUT_DIR = OUTPUT_DIR / "extracted_images"
IMAGES_OUTPUT_DIR.mkdir(exist_ok=True)


def find_image_pdfs(db, min_text_length: int = 100) -> list:
    """
    Find PDFs that are likely image-based (little to no text extracted).

    Args:
        db: Database session
        min_text_length: Documents with text shorter than this are considered image-based

    Returns:
        List of (document_id, efta_number, file_path) tuples
    """
    result = db.execute(text("""
        SELECT document_id, efta_number, file_path
        FROM documents
        WHERE (full_text IS NULL OR LENGTH(full_text) < :min_len)
        AND file_path IS NOT NULL
        ORDER BY efta_number
    """), {"min_len": min_text_length})

    return [(row[0], row[1], row[2]) for row in result]


def extract_and_catalog_images(db, document_id: int, efta_number: str, pdf_path: str, image_extractor: ImageExtractor) -> int:
    """
    Extract images from a PDF and catalog them in the database.

    Returns:
        Number of images extracted
    """
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        logger.warning(f"PDF not found: {pdf_path}")
        return 0

    # Create output directory for this document's images
    doc_output_dir = IMAGES_OUTPUT_DIR / efta_number
    doc_output_dir.mkdir(exist_ok=True)

    try:
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        images_extracted = 0

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

                    # Save image
                    image_filename = f"{efta_number}_p{page_num + 1}_img{img_index + 1}.{image_ext}"
                    image_path = doc_output_dir / image_filename

                    with open(image_path, "wb") as img_file:
                        img_file.write(image_bytes)

                    # Calculate checksum
                    import hashlib
                    checksum = hashlib.sha256(image_bytes).hexdigest()

                    # Check if already in database
                    existing = db.query(MediaFile).filter(MediaFile.checksum == checksum).first()
                    if existing:
                        logger.debug(f"Duplicate image (by checksum): {image_filename}")
                        continue

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

                    db.add(media_file)
                    images_extracted += 1

                except Exception as e:
                    logger.error(f"Error extracting image {img_index} from page {page_num}: {e}")

        doc.close()

        # Also try to render each page as an image if no embedded images found
        if images_extracted == 0:
            logger.info(f"No embedded images in {efta_number}, rendering pages as images...")
            images_extracted = render_pages_as_images(db, document_id, efta_number, pdf_path, doc_output_dir)

        return images_extracted

    except Exception as e:
        logger.error(f"Failed to extract images from {efta_number}: {e}")
        return 0


def render_pages_as_images(db, document_id: int, efta_number: str, pdf_path: Path, output_dir: Path) -> int:
    """
    Render PDF pages as images when no embedded images are found.
    """
    try:
        import fitz

        doc = fitz.open(pdf_path)
        images_extracted = 0

        for page_num in range(doc.page_count):
            page = doc[page_num]

            # Render page at 150 DPI
            mat = fitz.Matrix(150/72, 150/72)
            pix = page.get_pixmap(matrix=mat)

            image_filename = f"{efta_number}_page{page_num + 1}.png"
            image_path = output_dir / image_filename

            pix.save(str(image_path))

            # Calculate checksum
            import hashlib
            with open(image_path, 'rb') as f:
                checksum = hashlib.sha256(f.read()).hexdigest()

            # Check if already in database
            existing = db.query(MediaFile).filter(MediaFile.checksum == checksum).first()
            if existing:
                continue

            # Determine orientation
            width, height = pix.width, pix.height
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

            db.add(media_file)
            images_extracted += 1

        doc.close()
        return images_extracted

    except Exception as e:
        logger.error(f"Failed to render pages for {efta_number}: {e}")
        return 0


def main():
    db = SessionLocal()
    image_extractor = ImageExtractor()

    # Find image-based PDFs
    print("Finding image-based PDFs...")
    image_pdfs = find_image_pdfs(db)
    print(f"Found {len(image_pdfs)} PDFs with little/no text content")

    if not image_pdfs:
        print("No image-based PDFs found!")
        db.close()
        return

    # Show sample
    print("\nSample documents:")
    for doc_id, efta, path in image_pdfs[:5]:
        print(f"  {efta}: {path}")

    response = input(f"\nExtract images from {len(image_pdfs)} PDFs? (yes/no): ")
    if response.lower() != 'yes':
        print("Aborted.")
        db.close()
        return

    # Process PDFs
    total_images = 0
    processed = 0

    print("\nExtracting images...")
    for i, (doc_id, efta, path) in enumerate(image_pdfs):
        if i % 20 == 0:
            print(f"Progress: {i}/{len(image_pdfs)} ({100*i//len(image_pdfs)}%)")

        count = extract_and_catalog_images(db, doc_id, efta, path, image_extractor)
        total_images += count
        processed += 1

        # Commit in batches
        if processed % 50 == 0:
            db.commit()
            logger.info(f"Committed batch: {processed} documents, {total_images} images")

    # Final commit
    db.commit()

    print(f"\nCompleted:")
    print(f"  Documents processed: {processed}")
    print(f"  Images extracted: {total_images}")
    print(f"  Images saved to: {IMAGES_OUTPUT_DIR}")

    # Show database count
    result = db.execute(text("SELECT COUNT(*) FROM media_files"))
    media_count = result.fetchone()[0]
    print(f"  Total media files in database: {media_count}")

    db.close()


if __name__ == '__main__':
    main()
