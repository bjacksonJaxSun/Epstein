"""
Process zip files from DataSet_9/zipped directory.

Iterates through each zip file, temporarily extracts PDFs,
runs the extraction pipeline, cleans up temp files, and moves
to the next zip. Prevents duplicate document processing via
EFTA number tracking in the database.
"""
import sys
import os
import time
import zipfile
import tempfile
import shutil
from pathlib import Path
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent))

from config import SessionLocal, Base, engine, BATCH_SIZE
from extractors import PDFExtractor, NERProcessor
from services import DatabaseService, DeduplicationService, RelationshipBuilder
from models import Document
import dateparser


ZIPPED_DIR = Path(__file__).parent.parent / "epstein_files" / "DataSet_9" / "zipped"


class ZipExtractionProcessor:
    """Processes zip files containing PDF documents for extraction."""

    def __init__(self):
        self.pdf_extractor = PDFExtractor()
        self.ner_processor = NERProcessor()
        self.db = SessionLocal()
        self.db_service = DatabaseService(self.db)
        self.dedup_service = DeduplicationService(self.db)
        self.relationship_builder = RelationshipBuilder(self.db)

        # Stats
        self.total_processed = 0
        self.total_skipped = 0
        self.total_errors = 0
        self.total_zips_completed = 0

    def close(self):
        if hasattr(self, 'db'):
            self.db.close()

    def get_processed_efta_numbers(self) -> set:
        """Load all EFTA numbers already in the database."""
        rows = self.db.query(Document.efta_number).all()
        return {row[0] for row in rows}

    def get_zip_files(self) -> list[Path]:
        """Get sorted list of zip files to process."""
        if not ZIPPED_DIR.exists():
            logger.error(f"Zipped directory does not exist: {ZIPPED_DIR}")
            return []
        zips = sorted(ZIPPED_DIR.glob("*.zip"))
        logger.info(f"Found {len(zips)} zip files in {ZIPPED_DIR}")
        return zips

    def extract_efta_from_filename(self, filename: str) -> str | None:
        """Extract EFTA number from a PDF filename."""
        import re
        match = re.search(r'(EFTA\d{8})', filename)
        return match.group(1) if match else None

    def process_single_pdf(self, pdf_path: Path, processed_eftas: set) -> bool:
        """
        Process a single PDF file through the extraction pipeline.

        Returns True if successfully processed, False otherwise.
        """
        start_time = time.time()
        filename = pdf_path.name

        # Check EFTA number from filename first (fast skip)
        efta = self.extract_efta_from_filename(filename)
        if efta and efta in processed_eftas:
            logger.debug(f"Skipping already-processed: {filename}")
            self.total_skipped += 1
            return False

        try:
            # Extract PDF text and metadata
            doc_data = self.pdf_extractor.extract(str(pdf_path))
            if not doc_data or not doc_data.get('efta_number'):
                logger.warning(f"No EFTA number extracted from: {filename}")
                self.total_errors += 1
                return False

            efta_number = doc_data['efta_number']

            # Double-check against database (authoritative dedup)
            if efta_number in processed_eftas:
                logger.debug(f"Skipping duplicate EFTA: {efta_number}")
                self.total_skipped += 1
                return False

            existing = self.db_service.get_document_by_efta(efta_number)
            if existing:
                logger.debug(f"Already in database: {efta_number}")
                processed_eftas.add(efta_number)
                self.total_skipped += 1
                return False

            # Insert document
            document = self.db_service.insert_document(doc_data)
            if not document:
                logger.error(f"Failed to insert document: {filename}")
                self.total_errors += 1
                return False

            # NER extraction
            people_inserted = 0
            orgs_inserted = 0
            locations_inserted = 0
            events_inserted = 0

            if doc_data.get('full_text'):
                entities = self.ner_processor.process(doc_data['full_text'])

                # People
                for person_name in entities.get('people', []):
                    role = entities.get('person_roles', {}).get(person_name)
                    person = self.db_service.get_or_create_person(
                        full_name=person_name,
                        primary_role=role,
                        first_mentioned_in_doc_id=document.document_id
                    )
                    if person:
                        people_inserted += 1

                # Organizations
                for org_name in entities.get('organizations', []):
                    org = self.db_service.insert_organization({
                        'organization_name': org_name,
                        'first_mentioned_in_doc_id': document.document_id
                    })
                    if org:
                        orgs_inserted += 1

                # Locations
                for loc_name in entities.get('locations', []):
                    loc = self.db_service.insert_location({
                        'location_name': loc_name,
                        'first_mentioned_in_doc_id': document.document_id
                    })
                    if loc:
                        locations_inserted += 1

                # Events
                events_data = self.ner_processor.extract_events(doc_data['full_text'])
                for event_data in events_data:
                    event_date = dateparser.parse(event_data.get('event_date', ''))
                    if not event_date:
                        continue
                    event = self.db_service.insert_event({
                        'event_type': event_data['event_type'],
                        'description': event_data.get('description'),
                        'event_date': event_date.date(),
                        'source_document_id': document.document_id,
                        'confidence_level': 'low'
                    })
                    if event:
                        events_inserted += 1
                        for participant_name in event_data.get('participants', []):
                            person = self.db_service.get_person_by_name(participant_name)
                            if person:
                                self.db_service.link_event_participant(
                                    event.event_id, person.person_id
                                )

            # Log extraction
            processing_time = int((time.time() - start_time) * 1000)
            self.db_service.log_extraction({
                'document_id': document.document_id,
                'extraction_type': 'full',
                'status': 'success',
                'entities_extracted': people_inserted + orgs_inserted + locations_inserted,
                'events_extracted': events_inserted,
                'processing_time_ms': processing_time
            })

            processed_eftas.add(efta_number)
            self.total_processed += 1

            logger.info(
                f"[{efta_number}] {people_inserted}p {orgs_inserted}o "
                f"{locations_inserted}l {events_inserted}e ({processing_time}ms)"
            )
            return True

        except Exception as e:
            logger.error(f"Error processing {filename}: {e}")
            self.total_errors += 1
            return False

    def process_zip(self, zip_path: Path, processed_eftas: set) -> dict:
        """
        Extract a single zip to a temp directory, process all PDFs, clean up.

        Returns stats dict for this zip.
        """
        zip_name = zip_path.name
        zip_stats = {'processed': 0, 'skipped': 0, 'errors': 0, 'total_pdfs': 0}

        logger.info(f"{'=' * 60}")
        logger.info(f"Processing zip: {zip_name} ({zip_path.stat().st_size / 1024 / 1024:.1f} MB)")
        logger.info(f"{'=' * 60}")

        # Create a temp directory for extraction
        temp_dir = Path(tempfile.mkdtemp(prefix=f"epstein_{zip_name}_"))

        try:
            # Extract zip contents
            logger.info(f"Extracting to temp directory: {temp_dir}")
            try:
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    zf.extractall(temp_dir)
            except zipfile.BadZipFile:
                logger.error(f"Bad zip file: {zip_name}")
                zip_stats['errors'] = 1
                return zip_stats

            # Find all PDFs (may be nested in subdirectories)
            pdf_files = sorted(temp_dir.rglob("*.pdf"))
            zip_stats['total_pdfs'] = len(pdf_files)
            logger.info(f"Found {len(pdf_files)} PDF files in {zip_name}")

            if not pdf_files:
                logger.warning(f"No PDF files found in {zip_name}")
                return zip_stats

            # Pre-filter: check filenames against known EFTA numbers
            new_pdfs = []
            for pdf in pdf_files:
                efta = self.extract_efta_from_filename(pdf.name)
                if efta and efta in processed_eftas:
                    zip_stats['skipped'] += 1
                    self.total_skipped += 1
                else:
                    new_pdfs.append(pdf)

            if not new_pdfs:
                logger.info(f"All {len(pdf_files)} PDFs already processed, skipping zip")
                return zip_stats

            logger.info(f"Processing {len(new_pdfs)} new PDFs (skipped {zip_stats['skipped']} known)")

            # Process PDFs in batches
            for i in range(0, len(new_pdfs), BATCH_SIZE):
                batch = new_pdfs[i:i + BATCH_SIZE]
                batch_num = i // BATCH_SIZE + 1
                total_batches = (len(new_pdfs) - 1) // BATCH_SIZE + 1
                logger.info(f"Batch {batch_num}/{total_batches} ({len(batch)} files)")

                for pdf_path in batch:
                    success = self.process_single_pdf(pdf_path, processed_eftas)
                    if success:
                        zip_stats['processed'] += 1
                    elif not success:
                        # Could be skip or error - stats tracked in process_single_pdf
                        pass

                # Commit after each batch
                try:
                    self.db.commit()
                except Exception as e:
                    logger.error(f"Batch commit error: {e}")
                    self.db.rollback()

        finally:
            # Always clean up temp directory
            logger.info(f"Cleaning up temp directory: {temp_dir}")
            try:
                shutil.rmtree(temp_dir)
                logger.info("Temp directory cleaned up successfully")
            except Exception as e:
                logger.warning(f"Failed to clean up temp dir {temp_dir}: {e}")

        self.total_zips_completed += 1
        logger.info(
            f"Zip complete: {zip_name} - "
            f"{zip_stats['processed']} processed, "
            f"{zip_stats['skipped']} skipped, "
            f"{zip_stats['total_pdfs']} total PDFs"
        )
        return zip_stats

    def run(self, start_from: int = 0, limit: int = None):
        """
        Main entry point. Process all zip files.

        Args:
            start_from: Index of first zip to process (0-based). Useful for resuming.
            limit: Maximum number of zips to process. None = all.
        """
        # Initialize database tables
        Base.metadata.create_all(bind=engine)

        # Load already-processed EFTA numbers
        processed_eftas = self.get_processed_efta_numbers()
        logger.info(f"Database contains {len(processed_eftas)} already-processed documents")

        # Get zip files
        zip_files = self.get_zip_files()
        if not zip_files:
            logger.error("No zip files found. Exiting.")
            return

        # Apply start_from and limit
        zip_files = zip_files[start_from:]
        if limit:
            zip_files = zip_files[:limit]

        logger.info(f"Will process {len(zip_files)} zip files (starting from index {start_from})")

        start_time = time.time()

        for idx, zip_path in enumerate(zip_files):
            zip_num = start_from + idx + 1
            total = start_from + len(zip_files)
            logger.info(f"\n[ZIP {zip_num}/{total}] {zip_path.name}")

            try:
                self.process_zip(zip_path, processed_eftas)
            except KeyboardInterrupt:
                logger.warning("Interrupted by user. Saving progress...")
                self.db.commit()
                break
            except Exception as e:
                logger.error(f"Fatal error processing {zip_path.name}: {e}")
                self.db.rollback()
                continue

        # Post-processing
        elapsed = time.time() - start_time
        logger.info(f"\n{'=' * 60}")
        logger.info("POST-PROCESSING")
        logger.info(f"{'=' * 60}")

        # Build relationships
        logger.info("Building relationships from events...")
        try:
            rel_count = self.relationship_builder.build_relationships_from_events()
            logger.info(f"Built {rel_count} relationships")
        except Exception as e:
            logger.error(f"Relationship building error: {e}")

        # Deduplicate
        logger.info("Running entity deduplication...")
        try:
            merged = self.dedup_service.auto_merge_high_confidence(min_similarity=0.95)
            logger.info(f"Auto-merged {merged} high-confidence duplicates")
        except Exception as e:
            logger.error(f"Deduplication error: {e}")

        # Final stats
        stats = self.db_service.get_extraction_stats()
        logger.info(f"\n{'=' * 60}")
        logger.info("FINAL STATISTICS")
        logger.info(f"{'=' * 60}")
        logger.info(f"Zips completed:        {self.total_zips_completed}")
        logger.info(f"Documents processed:   {self.total_processed}")
        logger.info(f"Documents skipped:     {self.total_skipped}")
        logger.info(f"Errors:                {self.total_errors}")
        logger.info(f"Elapsed time:          {elapsed / 60:.1f} minutes")
        logger.info(f"")
        logger.info(f"Database totals:")
        logger.info(f"  Documents:           {stats['total_documents']}")
        logger.info(f"  People:              {stats['total_people']}")
        logger.info(f"  Organizations:       {stats['total_organizations']}")
        logger.info(f"  Locations:           {stats['total_locations']}")
        logger.info(f"  Events:              {stats['total_events']}")
        logger.info(f"  Relationships:       {stats['total_relationships']}")
        logger.info(f"{'=' * 60}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Process zip files from DataSet_9/zipped through the extraction pipeline."
    )
    parser.add_argument(
        '--start-from', type=int, default=0,
        help='Index of first zip file to process (0-based). Use to resume after interruption.'
    )
    parser.add_argument(
        '--limit', type=int, default=None,
        help='Maximum number of zip files to process. Default: all.'
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("EPSTEIN DOCUMENT ZIP EXTRACTION PIPELINE")
    logger.info("=" * 60)

    processor = ZipExtractionProcessor()
    try:
        processor.run(start_from=args.start_from, limit=args.limit)
    except KeyboardInterrupt:
        logger.warning("Process interrupted. Progress has been saved.")
    finally:
        processor.close()

    logger.info("Pipeline finished.")


if __name__ == "__main__":
    main()
