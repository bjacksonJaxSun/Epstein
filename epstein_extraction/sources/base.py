"""
Base classes for data source abstraction.

Provides the abstract interface and common utilities for downloading
PDFs from various sources (GeekenDev zip, Azure Blob, DOJ website).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Iterator, List, Dict
import time


class SourceType(Enum):
    """Enumeration of available data sources."""
    GEEKEN_ZIP = "geeken_zip"
    AZURE_BLOB = "azure_blob"
    DOJ_DIRECT = "doj_direct"


@dataclass
class FileMetadata:
    """Metadata about a file available from a source."""
    efta_number: str
    source_type: SourceType
    source_path: str  # Zip entry path, blob name, or URL
    doj_url: Optional[str] = None  # Direct DOJ URL for fallback
    file_size: Optional[int] = None
    checksum: Optional[str] = None


@dataclass
class DownloadResult:
    """Result of downloading a file from a source."""
    efta_number: str
    success: bool
    data: Optional[bytes] = None
    error_message: Optional[str] = None
    source_type: Optional[SourceType] = None
    download_time_ms: int = 0
    file_size: int = 0

    def __post_init__(self):
        if self.data and not self.file_size:
            self.file_size = len(self.data)


class DataSource(ABC):
    """
    Abstract base class for data sources.

    All concrete source implementations must inherit from this class
    and implement the required methods.
    """

    @property
    @abstractmethod
    def source_type(self) -> SourceType:
        """Return the type of this source."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the source is currently reachable."""
        pass

    @abstractmethod
    def download_file(self, metadata: FileMetadata) -> DownloadResult:
        """
        Download a single file.

        Args:
            metadata: File metadata including source path

        Returns:
            DownloadResult with data if successful, error message if not
        """
        pass

    def download_batch(self, metadata_list: List[FileMetadata]) -> Iterator[DownloadResult]:
        """
        Download multiple files efficiently.

        Default implementation downloads sequentially.
        Subclasses may override for more efficient batch operations.

        Args:
            metadata_list: List of file metadata to download

        Yields:
            DownloadResult for each file
        """
        for metadata in metadata_list:
            yield self.download_file(metadata)

    def validate_pdf(self, data: bytes) -> tuple[bool, str]:
        """
        Validate that data is a valid PDF.

        Args:
            data: Raw bytes to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not data:
            return False, "empty_data"
        if len(data) < 100:
            return False, f"too_small_{len(data)}b"
        if data[:5] != b"%PDF-":
            # Check if it's HTML (common error response)
            if data[:15].lower().startswith(b"<!doctype html") or data[:5].lower() == b"<html":
                return False, "html_response"
            return False, "not_pdf"
        return True, ""


@dataclass
class SourceRegistry:
    """
    Registry of available data sources with priority-based selection.

    Supports:
    - Primary/fallback source ordering
    - Health checking
    - Source-specific file availability tracking
    """

    _sources: Dict[SourceType, DataSource] = field(default_factory=dict)
    _priorities: Dict[SourceType, int] = field(default_factory=dict)
    _file_index: Dict[str, List[SourceType]] = field(default_factory=dict)

    def register(self, source: DataSource, priority: int = 100):
        """
        Register a source with given priority (lower = higher priority).

        Args:
            source: DataSource instance to register
            priority: Priority level (1 = highest, 100 = default)
        """
        self._sources[source.source_type] = source
        self._priorities[source.source_type] = priority

    def get_source(self, source_type: SourceType) -> Optional[DataSource]:
        """Get a specific source by type."""
        return self._sources.get(source_type)

    def get_sources_by_priority(self) -> List[DataSource]:
        """Get all sources sorted by priority (lowest number first)."""
        sorted_types = sorted(
            self._sources.keys(),
            key=lambda t: self._priorities.get(t, 100)
        )
        return [self._sources[t] for t in sorted_types]

    def get_available_sources(self) -> List[DataSource]:
        """Get all sources that are currently available, in priority order."""
        return [
            source for source in self.get_sources_by_priority()
            if source.is_available
        ]

    def get_source_for_file(self, efta_number: str) -> Optional[DataSource]:
        """
        Get the best available source for a specific file.

        First checks if the file is indexed to specific sources,
        then falls back to the first available source.

        Args:
            efta_number: EFTA identifier

        Returns:
            Best available DataSource or None
        """
        # Check cached index first
        if efta_number in self._file_index:
            for source_type in self._file_index[efta_number]:
                source = self._sources.get(source_type)
                if source and source.is_available:
                    return source

        # Fall back to first available source by priority
        available = self.get_available_sources()
        return available[0] if available else None

    def index_file(self, efta_number: str, source_type: SourceType):
        """Add a file to the source index."""
        if efta_number not in self._file_index:
            self._file_index[efta_number] = []
        if source_type not in self._file_index[efta_number]:
            self._file_index[efta_number].append(source_type)

    def download_with_fallback(
        self,
        efta_number: str,
        source_path: str,
        doj_url: Optional[str] = None
    ) -> DownloadResult:
        """
        Try downloading from sources in priority order until one succeeds.

        Args:
            efta_number: EFTA identifier
            source_path: Primary source path
            doj_url: DOJ URL for last resort fallback

        Returns:
            DownloadResult from the first successful source
        """
        errors = []

        for source in self.get_available_sources():
            metadata = FileMetadata(
                efta_number=efta_number,
                source_type=source.source_type,
                source_path=doj_url if source.source_type == SourceType.DOJ_DIRECT else source_path,
                doj_url=doj_url,
            )

            result = source.download_file(metadata)
            if result.success:
                return result
            errors.append(f"{source.source_type.value}:{result.error_message}")

        # All sources failed
        return DownloadResult(
            efta_number=efta_number,
            success=False,
            error_message=f"all_sources_failed:[{';'.join(errors)}]"
        )
