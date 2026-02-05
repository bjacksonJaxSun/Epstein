"""
E-Discovery Load File Parser for Concordance DAT and Opticon OPT formats

Parses standard litigation load files to efficiently index and access documents.
"""
import csv
import re
from pathlib import Path
from typing import Dict, List, Optional, Iterator, Tuple
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class DocumentRecord:
    """Represents a single document from the load files"""
    bates_begin: str
    bates_end: str
    volume: str
    relative_path: str
    absolute_path: Optional[Path] = None
    is_first_page: bool = True
    page_count: int = 1
    metadata: Dict = field(default_factory=dict)

    @property
    def efta_number(self) -> str:
        """Extract EFTA number from Bates number"""
        return self.bates_begin

    @property
    def document_id(self) -> str:
        """Alias for bates_begin"""
        return self.bates_begin


class LoadFileParser:
    """
    Parser for e-discovery load files (Concordance DAT and Opticon OPT)

    Supports:
    - Concordance DAT files (þ-delimited with þ text qualifiers)
    - Opticon OPT files (comma-delimited image references)
    """

    # Concordance delimiters
    CONCORDANCE_FIELD_DELIMITER = chr(0x14)  # ASCII 20
    CONCORDANCE_TEXT_QUALIFIER = 'þ'  # Thorn character (þ)

    def __init__(self, base_path: Path = None):
        """
        Initialize parser

        Args:
            base_path: Base directory for resolving relative paths
        """
        self.base_path = Path(base_path) if base_path else None
        self.documents: Dict[str, DocumentRecord] = {}
        self.dat_headers: List[str] = []
        self.opt_records: List[Dict] = []

    def parse_volume(self, volume_path: Path) -> int:
        """
        Parse all load files in a volume directory

        Args:
            volume_path: Path to volume directory (e.g., VOL00001)

        Returns:
            Number of documents parsed
        """
        volume_path = Path(volume_path)

        if not volume_path.exists():
            raise FileNotFoundError(f"Volume path not found: {volume_path}")

        # Set base path for resolving relative paths
        self.base_path = volume_path

        # Find DATA directory
        data_dir = volume_path / "DATA"
        if not data_dir.exists():
            # Try without DATA subdirectory
            data_dir = volume_path

        # Parse OPT file first (has path mappings)
        opt_files = list(data_dir.glob("*.OPT")) + list(data_dir.glob("*.opt"))
        for opt_file in opt_files:
            logger.info(f"Parsing OPT file: {opt_file.name}")
            self.parse_opt_file(opt_file)

        # Parse DAT file (has metadata)
        dat_files = list(data_dir.glob("*.DAT")) + list(data_dir.glob("*.dat"))
        for dat_file in dat_files:
            logger.info(f"Parsing DAT file: {dat_file.name}")
            self.parse_dat_file(dat_file)

        logger.info(f"Parsed {len(self.documents)} documents from {volume_path.name}")
        return len(self.documents)

    def parse_opt_file(self, opt_path: Path) -> int:
        """
        Parse Opticon OPT file

        OPT Format (comma-delimited):
        BATES_NUMBER,VOLUME,RELATIVE_PATH,FIRST_PAGE_FLAG,BOX,FOLDER,PAGE_COUNT

        Args:
            opt_path: Path to OPT file

        Returns:
            Number of records parsed
        """
        opt_path = Path(opt_path)
        records_parsed = 0

        with open(opt_path, 'r', encoding='utf-8', errors='replace') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    parts = line.split(',')
                    if len(parts) < 3:
                        logger.warning(f"OPT line {line_num}: insufficient fields")
                        continue

                    bates_number = parts[0].strip()
                    volume = parts[1].strip() if len(parts) > 1 else ''
                    relative_path = parts[2].strip() if len(parts) > 2 else ''
                    is_first_page = parts[3].strip().upper() == 'Y' if len(parts) > 3 else True
                    # box = parts[4] if len(parts) > 4 else ''
                    # folder = parts[5] if len(parts) > 5 else ''
                    page_count = int(parts[6]) if len(parts) > 6 and parts[6].strip().isdigit() else 1

                    # Normalize path separators
                    relative_path = relative_path.replace('\\', '/')

                    # Resolve absolute path
                    absolute_path = None
                    if self.base_path and relative_path:
                        absolute_path = self.base_path / relative_path

                    # Create or update document record
                    if bates_number not in self.documents:
                        self.documents[bates_number] = DocumentRecord(
                            bates_begin=bates_number,
                            bates_end=bates_number,
                            volume=volume,
                            relative_path=relative_path,
                            absolute_path=absolute_path,
                            is_first_page=is_first_page,
                            page_count=page_count
                        )
                    else:
                        # Update existing record
                        doc = self.documents[bates_number]
                        doc.relative_path = relative_path
                        doc.absolute_path = absolute_path
                        doc.volume = volume
                        doc.is_first_page = is_first_page
                        doc.page_count = page_count

                    self.opt_records.append({
                        'bates_number': bates_number,
                        'volume': volume,
                        'relative_path': relative_path,
                        'is_first_page': is_first_page,
                        'page_count': page_count
                    })

                    records_parsed += 1

                except Exception as e:
                    logger.warning(f"OPT line {line_num}: parse error - {e}")
                    continue

        logger.info(f"Parsed {records_parsed} records from OPT file")
        return records_parsed

    def parse_dat_file(self, dat_path: Path) -> int:
        """
        Parse Concordance DAT file

        DAT Format (þ-delimited with þ text qualifiers):
        þField1þ<delim>þField2þ<delim>þField3þ

        Args:
            dat_path: Path to DAT file

        Returns:
            Number of records parsed
        """
        dat_path = Path(dat_path)
        records_parsed = 0

        with open(dat_path, 'rb') as f:
            content = f.read()

        # Decode with UTF-8
        text = content.decode('utf-8', errors='replace')

        # Split into lines
        lines = text.split('\n')

        for line_num, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            try:
                # Parse Concordance format: þField1þ<delim>þField2þ
                # Remove leading/trailing qualifiers and split by delimiter
                fields = self._parse_concordance_line(line)

                if not fields:
                    continue

                # First line is header
                if line_num == 0 and self._looks_like_header(fields):
                    self.dat_headers = [f.strip() for f in fields]
                    logger.debug(f"DAT headers: {self.dat_headers}")
                    continue

                # Parse data row
                if self.dat_headers:
                    row_data = dict(zip(self.dat_headers, fields))
                else:
                    # Assume Begin Bates, End Bates format if no headers
                    row_data = {
                        'Begin Bates': fields[0] if len(fields) > 0 else '',
                        'End Bates': fields[1] if len(fields) > 1 else fields[0] if fields else ''
                    }

                # Extract Bates numbers
                bates_begin = row_data.get('Begin Bates', row_data.get('BEGBATES', '')).strip()
                bates_end = row_data.get('End Bates', row_data.get('ENDBATES', bates_begin)).strip()

                if not bates_begin:
                    continue

                # Create or update document record
                if bates_begin in self.documents:
                    doc = self.documents[bates_begin]
                    doc.bates_end = bates_end
                    doc.metadata.update(row_data)
                else:
                    self.documents[bates_begin] = DocumentRecord(
                        bates_begin=bates_begin,
                        bates_end=bates_end,
                        volume='',
                        relative_path='',
                        metadata=row_data
                    )

                records_parsed += 1

            except Exception as e:
                logger.warning(f"DAT line {line_num}: parse error - {e}")
                continue

        logger.info(f"Parsed {records_parsed} records from DAT file")
        return records_parsed

    def _parse_concordance_line(self, line: str) -> List[str]:
        """
        Parse a Concordance-formatted line

        Format: þField1þ<delim>þField2þ<delim>þField3þ
        Where <delim> is ASCII 20 (0x14)
        """
        fields = []

        # Split by field delimiter (ASCII 20)
        raw_fields = line.split(self.CONCORDANCE_FIELD_DELIMITER)

        for field in raw_fields:
            # Remove text qualifiers (þ) from start and end
            field = field.strip()
            if field.startswith(self.CONCORDANCE_TEXT_QUALIFIER):
                field = field[1:]
            if field.endswith(self.CONCORDANCE_TEXT_QUALIFIER):
                field = field[:-1]
            fields.append(field)

        return fields

    def _looks_like_header(self, fields: List[str]) -> bool:
        """Check if fields look like header row"""
        header_indicators = ['bates', 'begin', 'end', 'date', 'from', 'to', 'subject', 'custodian']
        for field in fields:
            if any(ind in field.lower() for ind in header_indicators):
                return True
        return False

    def get_document(self, bates_number: str) -> Optional[DocumentRecord]:
        """
        Get document by Bates number

        Args:
            bates_number: Document Bates number (e.g., EFTA00000001)

        Returns:
            DocumentRecord or None
        """
        return self.documents.get(bates_number)

    def get_document_path(self, bates_number: str) -> Optional[Path]:
        """
        Get absolute file path for a document

        Args:
            bates_number: Document Bates number

        Returns:
            Path to document file or None
        """
        doc = self.documents.get(bates_number)
        if doc and doc.absolute_path:
            return doc.absolute_path
        return None

    def iter_documents(self) -> Iterator[DocumentRecord]:
        """
        Iterate over all documents

        Yields:
            DocumentRecord objects
        """
        for doc in self.documents.values():
            yield doc

    def iter_document_paths(self, only_existing: bool = True) -> Iterator[Tuple[str, Path]]:
        """
        Iterate over document Bates numbers and paths

        Args:
            only_existing: Only yield paths that exist on disk

        Yields:
            Tuples of (bates_number, absolute_path)
        """
        for bates_number, doc in self.documents.items():
            if doc.absolute_path:
                if only_existing:
                    if doc.absolute_path.exists():
                        yield bates_number, doc.absolute_path
                else:
                    yield bates_number, doc.absolute_path

    def get_all_paths(self, only_existing: bool = True) -> List[Path]:
        """
        Get list of all document paths

        Args:
            only_existing: Only include paths that exist on disk

        Returns:
            List of Path objects
        """
        paths = []
        for _, path in self.iter_document_paths(only_existing=only_existing):
            paths.append(path)
        return paths

    def get_statistics(self) -> Dict:
        """
        Get parsing statistics

        Returns:
            Dictionary with statistics
        """
        total_docs = len(self.documents)
        docs_with_paths = sum(1 for d in self.documents.values() if d.absolute_path)
        existing_files = sum(1 for d in self.documents.values()
                           if d.absolute_path and d.absolute_path.exists())

        # Calculate total size of existing files
        total_size = 0
        for doc in self.documents.values():
            if doc.absolute_path and doc.absolute_path.exists():
                total_size += doc.absolute_path.stat().st_size

        return {
            'total_documents': total_docs,
            'documents_with_paths': docs_with_paths,
            'existing_files': existing_files,
            'missing_files': docs_with_paths - existing_files,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'dat_headers': self.dat_headers,
            'opt_records_count': len(self.opt_records)
        }

    def validate(self) -> Dict:
        """
        Validate parsed data

        Returns:
            Dictionary with validation results
        """
        issues = []

        # Check for documents without paths
        no_path = [b for b, d in self.documents.items() if not d.relative_path]
        if no_path:
            issues.append(f"{len(no_path)} documents without file paths")

        # Check for missing files
        missing = []
        for bates, doc in self.documents.items():
            if doc.absolute_path and not doc.absolute_path.exists():
                missing.append(bates)
        if missing:
            issues.append(f"{len(missing)} files not found on disk")

        # Check for duplicate Bates numbers (shouldn't happen with dict)
        # Check Bates number format
        invalid_bates = []
        bates_pattern = re.compile(r'^[A-Z]{2,4}\d{8,}$')
        for bates in self.documents.keys():
            if not bates_pattern.match(bates):
                invalid_bates.append(bates)
        if invalid_bates:
            issues.append(f"{len(invalid_bates)} non-standard Bates numbers")

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'documents_without_paths': no_path[:10],  # Sample
            'missing_files': missing[:10],  # Sample
            'invalid_bates_numbers': invalid_bates[:10]  # Sample
        }

    def to_dataframe(self):
        """
        Convert documents to pandas DataFrame

        Returns:
            pandas DataFrame
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for to_dataframe()")

        records = []
        for bates, doc in self.documents.items():
            record = {
                'bates_begin': doc.bates_begin,
                'bates_end': doc.bates_end,
                'volume': doc.volume,
                'relative_path': doc.relative_path,
                'absolute_path': str(doc.absolute_path) if doc.absolute_path else None,
                'is_first_page': doc.is_first_page,
                'page_count': doc.page_count,
                'file_exists': doc.absolute_path.exists() if doc.absolute_path else False
            }
            record.update(doc.metadata)
            records.append(record)

        return pd.DataFrame(records)


def parse_dataset(dataset_path: Path, volume_pattern: str = "VOL*") -> LoadFileParser:
    """
    Parse all volumes in a dataset

    Args:
        dataset_path: Path to dataset root directory
        volume_pattern: Glob pattern for volume directories

    Returns:
        LoadFileParser with all documents
    """
    dataset_path = Path(dataset_path)
    parser = LoadFileParser()

    # Find all volume directories
    volumes = sorted(dataset_path.glob(volume_pattern))

    if not volumes:
        # Maybe it's a single volume without subdirectories
        if (dataset_path / "DATA").exists():
            volumes = [dataset_path]
        else:
            # Look for nested structure
            for subdir in dataset_path.iterdir():
                if subdir.is_dir():
                    nested_volumes = sorted(subdir.glob(volume_pattern))
                    if nested_volumes:
                        volumes.extend(nested_volumes)
                    elif (subdir / "DATA").exists():
                        volumes.append(subdir)

    logger.info(f"Found {len(volumes)} volume(s) to parse")

    for volume in volumes:
        logger.info(f"Parsing volume: {volume}")
        parser.base_path = volume
        parser.parse_volume(volume)

    return parser


if __name__ == "__main__":
    # Test with DataSet 1
    import sys

    test_path = Path(r"D:\DataSet1_extracted\DataSet 1\DataSet 1\VOL00001")

    if test_path.exists():
        print(f"Parsing: {test_path}")
        parser = LoadFileParser(test_path)
        parser.parse_volume(test_path)

        # Print statistics
        stats = parser.get_statistics()
        print("\n" + "=" * 50)
        print("PARSING STATISTICS")
        print("=" * 50)
        for key, value in stats.items():
            print(f"{key}: {value}")

        # Validate
        validation = parser.validate()
        print("\n" + "=" * 50)
        print("VALIDATION")
        print("=" * 50)
        print(f"Valid: {validation['valid']}")
        if validation['issues']:
            print("Issues:")
            for issue in validation['issues']:
                print(f"  - {issue}")

        # Print sample documents
        print("\n" + "=" * 50)
        print("SAMPLE DOCUMENTS")
        print("=" * 50)
        for i, doc in enumerate(parser.iter_documents()):
            if i >= 5:
                break
            print(f"{doc.bates_begin}: {doc.relative_path}")
            if doc.absolute_path:
                print(f"  Exists: {doc.absolute_path.exists()}")
    else:
        print(f"Test path not found: {test_path}")
        print("Usage: python load_file_parser.py")
