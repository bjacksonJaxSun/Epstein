"""
Main orchestration script for document and image extraction

Supports two modes:
1. Load file mode: Parse OPT/DAT files for document indexing (e-discovery format)
2. Directory mode: Scan directories for PDF files (legacy mode)
"""
import sys
import time
import argparse
from pathlib import Path
from typing import List, Optional, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from loguru import logger

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    DATASET_9_DIR, SessionLocal, Base, engine,
    BATCH_SIZE, MAX_WORKERS, DATASETS, DEFAULT_DATASET
)
from extractors import PDFExtractor, ImageExtractor, NERProcessor, LoadFileParser
from services import DatabaseService, DeduplicationService, RelationshipBuilder
from models import Document, Person, Organization, Location, Event
import dateparser


class ExtractionOrchestrator:
    """Main orchestrator for extraction pipeline"""

    def __init__(self, dataset_key: str = None):
        """
        Initialize orchestrator

        Args:
            dataset_key: Key from DATASETS config (e.g., 'dataset_1', 'dataset_9')
        """
        self.pdf_extractor = PDFExtractor()
        self.image_extractor = ImageExtractor()
        self.ner_processor = NERProcessor()

        # Load file parser for e-discovery format datasets
        self.load_file_parser: Optional[LoadFileParser] = None

        # Dataset configuration
        self.dataset_key = dataset_key or DEFAULT_DATASET
        self.dataset_config = DATASETS.get(self.dataset_key, {})

        # Database session
        self.db = SessionLocal()
        self.db_service = DatabaseService(self.db)
        self.dedup_service = DeduplicationService(self.db)
        self.relationship_builder = RelationshipBuilder(self.db)

        # Statistics tracking
        self.stats = {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0,
        }

        logger.info("Extraction orchestrator initialized")
        if self.dataset_config:
            logger.info(f"Dataset: {self.dataset_config.get('name', self.dataset_key)}")

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

    def load_dataset(self) -> int:
        """
        Load dataset based on configuration

        Returns:
            Number of documents found
        """
        if not self.dataset_config:
            logger.error(f"Dataset '{self.dataset_key}' not found in configuration")
            return 0

        dataset_type = self.dataset_config.get('type', 'directory')
        dataset_path = self.dataset_config.get('path')

        if not dataset_path or not Path(dataset_path).exists():
            logger.error(f"Dataset path not found: {dataset_path}")
            return 0

        if dataset_type == 'load_file':
            return self._load_from_load_files(dataset_path)
        else:
            return self._load_from_directory(dataset_path)

    def _load_from_load_files(self, dataset_path: Path) -> int:
        """
        Load documents using OPT/DAT load files

        Args:
            dataset_path: Path to dataset root

        Returns:
            Number of documents loaded
        """
        logger.info(f"Loading dataset from load files: {dataset_path}")

        self.load_file_parser = LoadFileParser()
        volume_pattern = self.dataset_config.get('volume_pattern', 'VOL*')

        # Find and parse all volumes
        dataset_path = Path(dataset_path)
        volumes = sorted(dataset_path.glob(volume_pattern))

        if not volumes:
            # Check for nested structure (e.g., DataSet 1/DataSet 1/VOL00001)
            for subdir in dataset_path.iterdir():
                if subdir.is_dir():
                    nested_volumes = sorted(subdir.glob(volume_pattern))
                    volumes.extend(nested_volumes)

        if not volumes:
            logger.warning(f"No volumes found matching pattern '{volume_pattern}'")
            return 0

        total_docs = 0
        for volume in volumes:
            logger.info(f"Parsing volume: {volume.name}")
            try:
                count = self.load_file_parser.parse_volume(volume)
                total_docs += count
            except Exception as e:
                logger.error(f"Failed to parse volume {volume.name}: {e}")

        # Log statistics
        stats = self.load_file_parser.get_statistics()
        logger.info(f"Load file parsing complete:")
        logger.info(f"  Total documents indexed: {stats['total_documents']}")
        logger.info(f"  Files found on disk: {stats['existing_files']}")
        logger.info(f"  Missing files: {stats['missing_files']}")
        logger.info(f"  Total size: {stats['total_size_mb']} MB")

        return stats['existing_files']

    def _load_from_directory(self, dataset_path: Path) -> int:
        """
        Load documents by scanning directory for PDFs

        Args:
            dataset_path: Path to directory containing PDFs

        Returns:
            Number of documents found
        """
        logger.info(f"Loading dataset from directory: {dataset_path}")

        file_pattern = self.dataset_config.get('file_pattern', 'EFTA*.pdf')
        pdf_files = sorted(Path(dataset_path).glob(file_pattern))

        logger.info(f"Found {len(pdf_files)} PDF files")
        return len(pdf_files)

    def get_pdf_files(self, limit: int = None) -> List[Path]:
        """
        Get list of PDF files to process

        Args:
            limit: Maximum number of files (default: all)

        Returns:
            List of PDF file paths
        """
        if self.load_file_parser:
            # Use load file parser
            pdf_files = self.load_file_parser.get_all_paths(only_existing=True)
        else:
            # Fall back to directory scanning
            directory = self.dataset_config.get('path', DATASET_9_DIR)
            file_pattern = self.dataset_config.get('file_pattern', 'EFTA*.pdf')
            pdf_files = sorted(Path(directory).glob(file_pattern))

        if limit:
            pdf_files = pdf_files[:limit]

        logger.info(f"Selected {len(pdf_files)} PDF files to process")
        return pdf_files

    def get_document_metadata(self, pdf_path: Path) -> Dict:
        """
        Get metadata for a document from load files

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dictionary with metadata from load files
        """
        if not self.load_file_parser:
            return {}

        # Extract Bates number from filename
        bates_number = pdf_path.stem  # e.g., EFTA00000001

        doc_record = self.load_file_parser.get_document(bates_number)
        if doc_record:
            return {
                'bates_begin': doc_record.bates_begin,
                'bates_end': doc_record.bates_end,
                'volume': doc_record.volume,
                'page_count_from_load': doc_record.page_count,
                'load_file_metadata': doc_record.metadata,
            }
        return {}

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
            # Extract PDF content
            doc_data = self.pdf_extractor.extract(str(pdf_path))
            if not doc_data or not doc_data.get('efta_number'):
                logger.error(f"Failed to extract document: {pdf_path.name}")
                self.stats['failed'] += 1
                return False

            # Merge with load file metadata if available
            load_metadata = self.get_document_metadata(pdf_path)
            if load_metadata:
                doc_data['bates_begin'] = load_metadata.get('bates_begin')
                doc_data['bates_end'] = load_metadata.get('bates_end')
                doc_data['volume'] = load_metadata.get('volume')
                # Store any additional metadata from load files
                if load_metadata.get('load_file_metadata'):
                    doc_data['load_file_metadata'] = load_metadata['load_file_metadata']

            # Insert document into database
            document = self.db_service.insert_document(doc_data)
            if not document:
                logger.error(f"Failed to insert document: {pdf_path.name}")
                self.stats['failed'] += 1
                return False

            # Extract entities using NER (only if we have meaningful text)
            if doc_data.get('full_text') and len(doc_data['full_text'].strip()) > 50:
                self._process_entities(document, doc_data)
            else:
                # For image-heavy documents with little text, log it
                logger.debug(f"Minimal text extracted from {pdf_path.name} ({len(doc_data.get('full_text', ''))} chars)")

            # Log extraction results
            processing_time = int((time.time() - start_time) * 1000)
            self.db_service.log_extraction({
                'document_id': document.document_id,
                'extraction_type': 'full',
                'status': 'success',
                'processing_time_ms': processing_time
            })

            self.stats['processed'] += 1
            self.stats['successful'] += 1

            logger.debug(f"Processed {pdf_path.name} ({processing_time}ms)")
            return True

        except Exception as e:
            logger.error(f"Error processing {pdf_path.name}: {e}")
            self.stats['failed'] += 1
            return False

    def _process_entities(self, document, doc_data: Dict):
        """
        Extract and store entities from document text

        Args:
            document: Database document object
            doc_data: Extracted document data
        """
        entities = self.ner_processor.process(doc_data['full_text'])

        # Insert people
        people_inserted = 0
        for person_name in entities['people']:
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
                for participant_name in event_data['participants']:
                    person = self.db_service.get_person_by_name(participant_name)
                    if person:
                        self.db_service.link_event_participant(
                            event.event_id,
                            person.person_id
                        )

        logger.debug(
            f"Entities: {people_inserted} people, {orgs_inserted} orgs, "
            f"{locations_inserted} locations, {events_inserted} events"
        )

    def process_batch(self, pdf_files: List[Path], use_parallel: bool = True):
        """
        Process a batch of PDF files

        Args:
            pdf_files: List of PDF paths
            use_parallel: Use parallel processing
        """
        logger.info(f"Processing batch of {len(pdf_files)} files...")

        if use_parallel and MAX_WORKERS > 1:
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
                            future.result()
                        except Exception as e:
                            logger.error(f"Error processing {pdf_file.name}: {e}")
                        pbar.update(1)
        else:
            # Sequential processing
            for pdf_file in tqdm(pdf_files, desc="Processing PDFs"):
                self.process_single_document(pdf_file)

    def extract_all_documents(self, limit: int = None, use_parallel: bool = True):
        """
        Extract all documents in batches

        Args:
            limit: Maximum number of documents to process
            use_parallel: Use parallel processing
        """
        # Load dataset first
        total_available = self.load_dataset()
        if total_available == 0:
            logger.error("No documents found to process")
            return

        # Get files to process
        pdf_files = self.get_pdf_files(limit=limit)

        if not pdf_files:
            logger.error("No PDF files to process")
            return

        logger.info(f"Starting extraction of {len(pdf_files)} documents")

        # Process in batches
        for i in range(0, len(pdf_files), BATCH_SIZE):
            batch = pdf_files[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            total_batches = (len(pdf_files) - 1) // BATCH_SIZE + 1
            logger.info(f"Processing batch {batch_num} of {total_batches}")
            self.process_batch(batch, use_parallel=use_parallel)

        logger.info("Document extraction complete")
        self._print_extraction_stats()

    def _print_extraction_stats(self):
        """Print extraction statistics"""
        logger.info("\n" + "-" * 40)
        logger.info("EXTRACTION RESULTS")
        logger.info("-" * 40)
        logger.info(f"Processed:  {self.stats['processed']}")
        logger.info(f"Successful: {self.stats['successful']}")
        logger.info(f"Failed:     {self.stats['failed']}")
        logger.info(f"Skipped:    {self.stats['skipped']}")
        logger.info("-" * 40)

    def build_relationships(self):
        """Build relationships between entities"""
        logger.info("Building relationships...")

        event_rels = self.relationship_builder.build_relationships_from_events()
        logger.info(f"Built {event_rels} relationships from events")

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
        logger.info("DATABASE STATISTICS")
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

    def print_load_file_summary(self):
        """Print summary of loaded documents from load files"""
        if not self.load_file_parser:
            logger.info("No load file parser initialized")
            return

        stats = self.load_file_parser.get_statistics()
        validation = self.load_file_parser.validate()

        logger.info("\n" + "=" * 60)
        logger.info("LOAD FILE SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Documents:       {stats['total_documents']}")
        logger.info(f"Documents with Paths:  {stats['documents_with_paths']}")
        logger.info(f"Existing Files:        {stats['existing_files']}")
        logger.info(f"Missing Files:         {stats['missing_files']}")
        logger.info(f"Total Size:            {stats['total_size_mb']} MB")
        logger.info(f"DAT Headers:           {stats['dat_headers']}")

        if not validation['valid']:
            logger.warning("Validation Issues:")
            for issue in validation['issues']:
                logger.warning(f"  - {issue}")

        logger.info("=" * 60 + "\n")


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Epstein Document Extraction Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                          # Process default dataset (dataset_1)
  python main.py --dataset dataset_9      # Process dataset_9
  python main.py --limit 100              # Process first 100 documents
  python main.py --no-parallel            # Disable parallel processing
  python main.py --info                   # Show dataset info without processing
        """
    )

    parser.add_argument(
        '--dataset', '-d',
        choices=list(DATASETS.keys()),
        default=DEFAULT_DATASET,
        help='Dataset to process'
    )

    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=None,
        help='Limit number of documents to process'
    )

    parser.add_argument(
        '--no-parallel',
        action='store_true',
        help='Disable parallel processing'
    )

    parser.add_argument(
        '--skip-relationships',
        action='store_true',
        help='Skip relationship building phase'
    )

    parser.add_argument(
        '--skip-dedup',
        action='store_true',
        help='Skip deduplication phase'
    )

    parser.add_argument(
        '--info',
        action='store_true',
        help='Show dataset info without processing'
    )

    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_args()

    logger.info("=" * 60)
    logger.info("EPSTEIN DOCUMENT EXTRACTION PIPELINE")
    logger.info("=" * 60)

    # Initialize orchestrator with selected dataset
    orchestrator = ExtractionOrchestrator(dataset_key=args.dataset)

    # Info mode - just show dataset summary
    if args.info:
        orchestrator.load_dataset()
        orchestrator.print_load_file_summary()
        return

    # Initialize database
    orchestrator.initialize_database()

    # Extract documents
    logger.info("\nPHASE 1: Document Extraction")
    orchestrator.extract_all_documents(
        limit=args.limit,
        use_parallel=not args.no_parallel
    )

    # Build relationships
    if not args.skip_relationships:
        logger.info("\nPHASE 2: Relationship Building")
        orchestrator.build_relationships()

    # Deduplicate entities
    if not args.skip_dedup:
        logger.info("\nPHASE 3: Deduplication")
        orchestrator.deduplicate_entities()

    # Print final statistics
    orchestrator.print_statistics()

    logger.info("Extraction pipeline complete!")


if __name__ == "__main__":
    main()
