"""
Load a dataset into the database.
Generic script that can load any dataset by path.
"""
import sys
import os
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from config import SessionLocal
from extractors import PDFExtractor
from models import Document
from loguru import logger


def find_pdf_files(source_dir: str) -> dict:
    """Find all PDF files in the source directory."""
    source_files = {}
    for root, dirs, files in os.walk(source_dir):
        for f in files:
            if f.lower().endswith('.pdf'):
                efta = f.upper().replace('.PDF', '')
                source_files[efta] = Path(root) / f
    return source_files


def get_existing_eftas(db) -> set:
    """Get all EFTA numbers already in the database."""
    result = db.execute(text("SELECT efta_number FROM documents WHERE efta_number IS NOT NULL"))
    return set(row[0].upper() for row in result if row[0])


def load_documents(source_dir: str, batch_size: int = 50):
    """Load documents from source directory into the database."""
    db = SessionLocal()
    pdf_extractor = PDFExtractor()

    # Find all PDFs
    print(f"Scanning {source_dir}...")
    all_files = find_pdf_files(source_dir)
    print(f"Found {len(all_files)} PDF files")

    # Get existing EFTA numbers
    existing = get_existing_eftas(db)
    print(f"Already in database: {len(existing)} documents")

    # Filter to only missing files
    missing_files = {k: v for k, v in all_files.items() if k not in existing}
    print(f"To be loaded: {len(missing_files)} documents")

    if not missing_files:
        print("No new documents to load!")
        db.close()
        return 0, 0

    # Show sample
    print("\nSample files to load:")
    for efta in sorted(missing_files.keys())[:5]:
        print(f"  {efta}")

    response = input(f"\nLoad {len(missing_files)} documents? (yes/no): ")
    if response.lower() != 'yes':
        print("Aborted.")
        db.close()
        return 0, 0

    # Process files
    processed = 0
    failed = 0
    total = len(missing_files)
    file_list = list(missing_files.items())

    print("\nLoading documents...")
    for i, (efta, pdf_path) in enumerate(file_list):
        if i % 20 == 0:
            print(f"Progress: {i}/{total} ({100*i//total}%)")

        try:
            # Extract PDF content
            doc_data = pdf_extractor.extract(str(pdf_path))

            if not doc_data:
                logger.warning(f"Failed to extract: {efta}")
                failed += 1
                continue

            # Create document record
            document = Document(
                efta_number=doc_data.get('efta_number', efta),
                file_path=str(pdf_path),
                document_type=doc_data.get('document_type'),
                document_date=doc_data.get('document_date'),
                document_title=doc_data.get('title'),
                author=doc_data.get('author'),
                recipient=doc_data.get('recipient'),
                subject=doc_data.get('subject'),
                full_text=doc_data.get('text', ''),
                full_text_searchable=doc_data.get('text', '').lower() if doc_data.get('text') else '',
                page_count=doc_data.get('page_count', 1),
                file_size_bytes=pdf_path.stat().st_size if pdf_path.exists() else 0,
                is_redacted=doc_data.get('is_redacted', False),
                extraction_status='completed',
                extraction_confidence=doc_data.get('extraction_confidence', 0.8),
            )

            db.add(document)
            processed += 1

            # Commit in batches
            if processed % batch_size == 0:
                db.commit()
                logger.info(f"Committed batch: {processed} documents processed")

        except Exception as e:
            logger.error(f"Error processing {efta}: {e}")
            failed += 1
            db.rollback()

    # Final commit
    db.commit()
    db.close()

    print(f"\nCompleted:")
    print(f"  Processed: {processed}")
    print(f"  Failed: {failed}")

    return processed, failed


def main():
    if len(sys.argv) < 2:
        print("Usage: python load_dataset.py <source_directory>")
        print("Example: python load_dataset.py D:/DataSet2_extracted")
        sys.exit(1)

    source_dir = sys.argv[1]

    if not os.path.exists(source_dir):
        print(f"Error: Directory not found: {source_dir}")
        sys.exit(1)

    load_documents(source_dir)

    # Show final count
    db = SessionLocal()
    result = db.execute(text("SELECT COUNT(*) FROM documents"))
    total = result.fetchone()[0]
    print(f"\nTotal documents in database: {total}")
    db.close()


if __name__ == '__main__':
    main()
