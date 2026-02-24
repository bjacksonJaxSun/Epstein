"""
Source handlers for multi-source PDF download system.

This package provides abstract and concrete implementations for downloading
PDFs from various sources:

1. GeekenZipSource (Priority 1) - Fast HTTP range requests from zip archives
2. AzureBlobSource (Priority 2) - Azure Blob Storage downloads
3. DojDirectSource (Priority 3) - Direct DOJ website (last resort, rate-limited)

Usage:
    from sources import SourceRegistry, GeekenZipSource, AzureBlobSource, DojDirectSource

    registry = SourceRegistry()
    registry.register(GeekenZipSource(dataset_num=11), priority=1)
    registry.register(AzureBlobSource(...), priority=2)
    registry.register(DojDirectSource(), priority=3)

    # Get best available source for a file
    source = registry.get_source_for_file(efta_number)
    result = source.download_file(metadata)
"""

from .base import (
    DataSource,
    SourceType,
    FileMetadata,
    DownloadResult,
    SourceRegistry,
)
from .geeken_zip import GeekenZipSource
from .azure_blob import AzureBlobSource
from .doj_direct import DojDirectSource

__all__ = [
    # Base classes
    "DataSource",
    "SourceType",
    "FileMetadata",
    "DownloadResult",
    "SourceRegistry",
    # Concrete sources
    "GeekenZipSource",
    "AzureBlobSource",
    "DojDirectSource",
]
