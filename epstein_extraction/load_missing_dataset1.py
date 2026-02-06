"""
Load missing Dataset 1 documents into the database.
"""
import sys
import os
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from config import SessionLocal, DATASETS
from extractors import PDFExtractor
from models import Document
from loguru import logger


def find_missing_documents():
    """Find Dataset 1 documents that are not in the database."""
    db = SessionLocal()

    # Get all PDFs from source folder
    source_dir = Path(r'D:\DataSet1_extracted')
    source_files = {}
    for root, dirs, files in os.walk(source_dir):
        for f in files:
            if f.lower().endswith('.pdf'):
                efta = f.upper().replace('.PDF', '')
                source_files[efta] = Path(root) / f

    print(f"PDF files in source folder: {len(source_files)}")

    # Get all EFTA numbers in database for Dataset 1
    result = db.execute(text("""
        SELECT efta_number FROM documents
        WHERE file_path LIKE '%DataSet_1%'
           OR file_path LIKE '%Dataset_1%'
           OR file_path LIKE '%Dataset 1%'
    """))
    db_eftas = set(row[0].upper() for row in result if row[0])
    print(f"Dataset 1 documents in database: {len(db_eftas)}")

    # Find missing
    missing = {}
    for efta, path in source_files.items():
        if efta not in db_eftas:
            missing[efta] = path

    print(f"Missing from database: {len(missing)}")
    db.close()

    return missing


def load_missing_documents(missing_files: dict, batch_size: int = 50):
    """Load missing documents into the database."""
    db = SessionLocal()
    pdf_extractor = PDFExtractor()

    processed = 0
    failed = 0

    file_list = list(missing_files.items())

    total = len(file_list)
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

            # Check if already exists (by EFTA)
            existing = db.query(Document).filter(Document.efta_number == efta).first()
            if existing:
                logger.info(f"Already exists: {efta}")
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
    print("Finding missing Dataset 1 documents...")
    missing = find_missing_documents()

    if not missing:
        print("No missing documents found!")
        return

    print(f"\nFound {len(missing)} missing documents")
    print("Sample missing files:")
    for efta in sorted(missing.keys())[:10]:
        print(f"  {efta}: {missing[efta]}")

    response = input(f"\nLoad {len(missing)} missing documents? (yes/no): ")
    if response.lower() != 'yes':
        print("Aborted.")
        return

    print("\nLoading missing documents...")
    load_missing_documents(missing)

    # Verify
    db = SessionLocal()
    result = db.execute(text("""
        SELECT COUNT(*) FROM documents
        WHERE file_path LIKE '%DataSet_1%'
           OR file_path LIKE '%Dataset_1%'
           OR file_path LIKE '%Dataset 1%'
    """))
    new_count = result.fetchone()[0]
    print(f"\nDataset 1 documents now in database: {new_count}")
    db.close()


if __name__ == '__main__':
    main()
