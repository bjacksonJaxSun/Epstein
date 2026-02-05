"""
Continuous processor that can run while files are being downloaded
Monitors directory for new files and processes them as they arrive
"""
import sys
import time
from pathlib import Path
from typing import Set, List
from datetime import datetime
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent))

from config import DATASET_9_DIR, SessionLocal
from main import ExtractionOrchestrator

class ContinuousProcessor:
    """
    Process files continuously while downloads are happening
    """

    def __init__(self, watch_directory: Path = None):
        self.watch_dir = watch_directory or DATASET_9_DIR
        self.orchestrator = ExtractionOrchestrator()
        self.processed_files: Set[str] = set()
        self.processing = True

        # Load already processed files from database
        self._load_processed_files()

        logger.info(f"Watching directory: {self.watch_dir}")
        logger.info(f"Already processed: {len(self.processed_files)} files")

    def _load_processed_files(self):
        """Load list of already processed files from database"""
        try:
            db = SessionLocal()
            from models import Document

            # Get all EFTA numbers already in database
            processed_docs = db.query(Document.efta_number).all()
            self.processed_files = {doc[0] for doc in processed_docs}

            db.close()
            logger.info(f"Loaded {len(self.processed_files)} already-processed files from database")

        except Exception as e:
            logger.warning(f"Could not load processed files from database: {e}")
            self.processed_files = set()

    def _is_file_ready(self, file_path: Path) -> bool:
        """
        Check if file is ready for processing (not being written)

        Args:
            file_path: Path to file

        Returns:
            True if file is ready, False if still being written
        """
        try:
            # Quick check: Can we open file for reading?
            try:
                with open(file_path, 'rb') as f:
                    f.read(1)
                return True
            except (PermissionError, IOError):
                logger.debug(f"File locked: {file_path.name}")
                return False

        except Exception as e:
            logger.debug(f"Error checking file readiness: {e}")
            return False

    def _get_new_files(self) -> List[Path]:
        """
        Get list of new files that haven't been processed yet

        Returns:
            List of new PDF files
        """
        all_pdfs = sorted(self.watch_dir.glob("EFTA*.pdf"))
        new_files = []

        for pdf_file in all_pdfs:
            # Extract EFTA number from filename
            efta_number = pdf_file.stem  # EFTA00068047

            # Skip if already processed
            if efta_number in self.processed_files:
                continue

            # Check if file is ready for processing
            if self._is_file_ready(pdf_file):
                new_files.append(pdf_file)
            else:
                logger.debug(f"Skipping (not ready): {pdf_file.name}")

        return new_files

    def _mark_as_processed(self, efta_number: str):
        """Mark file as processed"""
        self.processed_files.add(efta_number)

    def process_batch(self, files: List[Path]):
        """Process a batch of files"""
        if not files:
            return

        logger.info(f"Processing batch of {len(files)} new files...")

        for pdf_file in files:
            try:
                success = self.orchestrator.process_single_document(pdf_file)

                if success:
                    self._mark_as_processed(pdf_file.stem)
                else:
                    logger.warning(f"Failed to process: {pdf_file.name}")

            except Exception as e:
                logger.error(f"Error processing {pdf_file.name}: {e}")

    def run_continuous(self, scan_interval: int = 60, batch_size: int = 50):
        """
        Run continuous processing mode

        Args:
            scan_interval: Seconds between directory scans
            batch_size: Number of files to process per batch
        """
        logger.info("Starting continuous processing mode...")
        logger.info(f"Scan interval: {scan_interval} seconds")
        logger.info(f"Batch size: {batch_size} files")
        logger.info("Press Ctrl+C to stop\n")

        try:
            while self.processing:
                # Get new files
                new_files = self._get_new_files()

                if new_files:
                    logger.info(f"Found {len(new_files)} new files")

                    # Process in batches
                    for i in range(0, len(new_files), batch_size):
                        batch = new_files[i:i + batch_size]
                        self.process_batch(batch)

                    # Print current stats
                    self.orchestrator.print_statistics()
                else:
                    logger.info(f"No new files. Waiting {scan_interval} seconds...")

                # Wait before next scan
                time.sleep(scan_interval)

        except KeyboardInterrupt:
            logger.info("\n\nStopping continuous processor...")
            self.processing = False

    def run_once(self):
        """
        Process all new files once and exit

        Useful for cron jobs or scheduled tasks
        """
        logger.info("Running single-pass processing...")

        new_files = self._get_new_files()

        if new_files:
            logger.info(f"Found {len(new_files)} new files to process")
            self.process_batch(new_files)
            self.orchestrator.print_statistics()
        else:
            logger.info("No new files found")

    def get_progress_report(self) -> dict:
        """
        Get current progress report

        Returns:
            Dictionary with progress statistics
        """
        all_pdfs = list(self.watch_dir.glob("EFTA*.pdf"))
        total_files = len(all_pdfs)
        processed_count = len(self.processed_files)
        pending_count = total_files - processed_count

        stats = self.orchestrator.db_service.get_extraction_stats()

        return {
            'timestamp': datetime.now().isoformat(),
            'total_files_downloaded': total_files,
            'files_processed': processed_count,
            'files_pending': pending_count,
            'progress_percentage': (processed_count / total_files * 100) if total_files > 0 else 0,
            'database_stats': stats
        }

    def print_progress(self):
        """Print current progress"""
        report = self.get_progress_report()

        logger.info("\n" + "=" * 70)
        logger.info("CONTINUOUS PROCESSING PROGRESS")
        logger.info("=" * 70)
        logger.info(f"Time:                  {report['timestamp']}")
        logger.info(f"Total Files Downloaded: {report['total_files_downloaded']}")
        logger.info(f"Files Processed:        {report['files_processed']}")
        logger.info(f"Files Pending:          {report['files_pending']}")
        logger.info(f"Progress:               {report['progress_percentage']:.2f}%")
        logger.info("-" * 70)
        logger.info(f"Database Documents:     {report['database_stats']['total_documents']}")
        logger.info(f"Database People:        {report['database_stats']['total_people']}")
        logger.info(f"Database Events:        {report['database_stats']['total_events']}")
        logger.info(f"Database Relationships: {report['database_stats']['total_relationships']}")
        logger.info("=" * 70 + "\n")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Continuous PDF extraction processor')
    parser.add_argument(
        '--mode',
        choices=['continuous', 'once'],
        default='continuous',
        help='Processing mode (default: continuous)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='Scan interval in seconds (default: 60)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        help='Files to process per batch (default: 50)'
    )
    parser.add_argument(
        '--directory',
        type=str,
        default=None,
        help='Directory to watch (default: DataSet_9)'
    )

    args = parser.parse_args()

    # Initialize processor
    watch_dir = Path(args.directory) if args.directory else DATASET_9_DIR
    processor = ContinuousProcessor(watch_directory=watch_dir)

    # Initialize database
    processor.orchestrator.initialize_database()

    # Run based on mode
    if args.mode == 'continuous':
        processor.run_continuous(
            scan_interval=args.interval,
            batch_size=args.batch_size
        )
    else:
        processor.run_once()


if __name__ == "__main__":
    main()
