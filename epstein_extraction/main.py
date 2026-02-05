"""
Main orchestration script for document and image extraction
"""
import sys
import time
from pathlib import Path
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from loguru import logger

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    DATASET_9_DIR, SessionLocal, Base, engine,
    BATCH_SIZE, MAX_WORKERS
)
from extractors import PDFExtractor, ImageExtractor, NERProcessor
from services import DatabaseService, DeduplicationService, RelationshipBuilder
from models import Document, Person, Organization, Location, Event
import dateparser

class ExtractionOrchestrator:
    """Main orchestrator for extraction pipeline"""

    def __init__(self):
        self.pdf_extractor = PDFExtractor()
        self.image_extractor = ImageExtractor()
        self.ner_processor = NERProcessor()

        # Database session
        self.db = SessionLocal()
        self.db_service = DatabaseService(self.db)
        self.dedup_service = DeduplicationService(self.db)
        self.relationship_builder = RelationshipBuilder(self.db)

        logger.info("Extraction orchestrator initialized")

    def __del__(self):
        """Cleanup"""
        if hasattr(self, 'db'):
            self.db.close()

    def initialize_database(self):
        """Create all database tables"""
        logger.info("Creating database tables...")
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise

    def get_pdf_files(self, directory: Path = None, limit: int = None) -> List[Path]:
        """
        Get list of PDF files to process

        Args:
            directory: Directory to search (default: DATASET_9_DIR)
            limit: Maximum number of files (default: all)

        Returns:
            List of PDF file paths
        """
        if directory is None:
            directory = DATASET_9_DIR

        pdf_files = sorted(directory.glob("EFTA*.pdf"))

        if limit:
            pdf_files = pdf_files[:limit]

        logger.info(f"Found {len(pdf_files)} PDF files to process")
        return pdf_files

    def process_single_document(self, pdf_path: Path) -> bool:
        """
        Process a single PDF document

        Args:
            pdf_path: Path to PDF file

        Returns:
            Success status
        """
        start_time = time.time()

        try:
            # Extract PDF text
            doc_data = self.pdf_extractor.extract(str(pdf_path))
            if not doc_data or not doc_data.get('efta_number'):
                logger.error(f"Failed to extract document: {pdf_path.name}")
                return False

            # Insert document into database
            document = self.db_service.insert_document(doc_data)
            if not document:
                logger.error(f"Failed to insert document: {pdf_path.name}")
                return False

            # Extract entities using NER
            if doc_data.get('full_text'):
                entities = self.ner_processor.process(doc_data['full_text'])

                # Insert people
                people_inserted = 0
                for person_name in entities['people']:
                    # Check for role
                    role = entities['person_roles'].get(person_name)

                    person = self.db_service.get_or_create_person(
                        full_name=person_name,
                        primary_role=role,
                        first_mentioned_in_doc_id=document.document_id
                    )

                    if person:
                        people_inserted += 1

                # Insert organizations
                orgs_inserted = 0
                for org_name in entities['organizations']:
                    org = self.db_service.insert_organization({
                        'organization_name': org_name,
                        'first_mentioned_in_doc_id': document.document_id
                    })
                    if org:
                        orgs_inserted += 1

                # Insert locations
                locations_inserted = 0
                for loc_name in entities['locations']:
                    loc = self.db_service.insert_location({
                        'location_name': loc_name,
                        'first_mentioned_in_doc_id': document.document_id
                    })
                    if loc:
                        locations_inserted += 1

                # Extract and insert events
                events_data = self.ner_processor.extract_events(doc_data['full_text'])
                events_inserted = 0
                for event_data in events_data:
                    # Parse date
                    event_date = dateparser.parse(event_data['event_date'])
                    if not event_date:
                        continue

                    event = self.db_service.insert_event({
                        'event_type': event_data['event_type'],
                        'description': event_data['description'],
                        'event_date': event_date.date(),
                        'source_document_id': document.document_id,
                        'confidence_level': 'low'
                    })

                    if event:
                        events_inserted += 1

                        # Link participants
                        for participant_name in event_data['participants']:
                            person = self.db_service.get_person_by_name(participant_name)
                            if person:
                                self.db_service.link_event_participant(
                                    event.event_id,
                                    person.person_id
                                )

                # Log extraction results
                processing_time = int((time.time() - start_time) * 1000)
                self.db_service.log_extraction({
                    'document_id': document.document_id,
                    'extraction_type': 'full',
                    'status': 'success',
                    'entities_extracted': people_inserted + orgs_inserted + locations_inserted,
                    'events_extracted': events_inserted,
                    'processing_time_ms': processing_time
                })

                logger.info(
                    f"Processed {pdf_path.name}: "
                    f"{people_inserted} people, {orgs_inserted} orgs, "
                    f"{locations_inserted} locations, {events_inserted} events "
                    f"({processing_time}ms)"
                )

            return True

        except Exception as e:
            logger.error(f"Error processing {pdf_path.name}: {e}")
            return False

    def process_batch(self, pdf_files: List[Path], use_parallel: bool = True):
        """
        Process a batch of PDF files

        Args:
            pdf_files: List of PDF paths
            use_parallel: Use parallel processing
        """
        logger.info(f"Processing batch of {len(pdf_files)} files...")

        if use_parallel:
            # Parallel processing
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {
                    executor.submit(self.process_single_document, pdf_file): pdf_file
                    for pdf_file in pdf_files
                }

                with tqdm(total=len(pdf_files), desc="Processing PDFs") as pbar:
                    for future in as_completed(futures):
                        pdf_file = futures[future]
                        try:
                            success = future.result()
                            pbar.update(1)
                        except Exception as e:
                            logger.error(f"Error processing {pdf_file.name}: {e}")
                            pbar.update(1)
        else:
            # Sequential processing
            for pdf_file in tqdm(pdf_files, desc="Processing PDFs"):
                self.process_single_document(pdf_file)

    def extract_all_documents(self, limit: int = None):
        """
        Extract all documents in batches

        Args:
            limit: Maximum number of documents to process
        """
        pdf_files = self.get_pdf_files(limit=limit)

        # Process in batches
        for i in range(0, len(pdf_files), BATCH_SIZE):
            batch = pdf_files[i:i + BATCH_SIZE]
            logger.info(f"Processing batch {i // BATCH_SIZE + 1} of {(len(pdf_files) - 1) // BATCH_SIZE + 1}")
            self.process_batch(batch)

        logger.info("Document extraction complete")

    def build_relationships(self):
        """Build relationships between entities"""
        logger.info("Building relationships...")

        event_rels = self.relationship_builder.build_relationships_from_events()
        logger.info(f"Built {event_rels} relationships from events")

        # comm_rels = self.relationship_builder.build_relationships_from_communications()
        # logger.info(f"Built {comm_rels} relationships from communications")

        logger.info("Relationship building complete")

    def deduplicate_entities(self):
        """Deduplicate entities"""
        logger.info("Deduplicating entities...")

        # Find merge suggestions
        suggestions = self.dedup_service.suggest_merges('person')
        logger.info(f"Found {len(suggestions)} potential person merges")

        # Auto-merge high confidence (95%+)
        merged = self.dedup_service.auto_merge_high_confidence(min_similarity=0.95)
        logger.info(f"Auto-merged {merged} high-confidence duplicates")

    def print_statistics(self):
        """Print extraction statistics"""
        stats = self.db_service.get_extraction_stats()

        logger.info("\n" + "=" * 60)
        logger.info("EXTRACTION STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Total Documents:       {stats['total_documents']}")
        logger.info(f"Extracted Documents:   {stats['extracted_documents']}")
        logger.info(f"Pending Documents:     {stats['pending_documents']}")
        logger.info(f"Total People:          {stats['total_people']}")
        logger.info(f"Total Organizations:   {stats['total_organizations']}")
        logger.info(f"Total Locations:       {stats['total_locations']}")
        logger.info(f"Total Events:          {stats['total_events']}")
        logger.info(f"Total Relationships:   {stats['total_relationships']}")
        logger.info(f"Total Media Files:     {stats['total_media_files']}")
        logger.info("=" * 60 + "\n")


def main():
    """Main entry point"""
    logger.info("Starting Epstein Document Extraction Pipeline")
    logger.info("=" * 60)

    orchestrator = ExtractionOrchestrator()

    # Initialize database
    orchestrator.initialize_database()

    # Extract documents
    # Start with first 10 for testing
    logger.info("PHASE 1: Document Extraction")
    orchestrator.extract_all_documents(limit=10)

    # Build relationships
    logger.info("\nPHASE 2: Relationship Building")
    orchestrator.build_relationships()

    # Deduplicate entities
    logger.info("\nPHASE 3: Deduplication")
    orchestrator.deduplicate_entities()

    # Print final statistics
    orchestrator.print_statistics()

    logger.info("Extraction pipeline complete!")


if __name__ == "__main__":
    main()
