"""
Azure Blob Storage Source Handler.

Downloads PDFs from Azure Blob Storage. This is the secondary (Priority 2)
source, used when GeekenDev mirror is unavailable or missing files.
"""

import os
import re
import time
from typing import Iterator, List, Optional
from loguru import logger

from .base import DataSource, SourceType, FileMetadata, DownloadResult


class AzureBlobSource(DataSource):
    """
    Download from Azure Blob Storage.

    Uses the Azure SDK to download blobs directly from Azure storage.
    Requires Azure credentials (account name and key).
    """

    # Default Azure paths for each dataset
    AZURE_PREFIXES = {
        9: "VOL00010/VOL00010/DataSet_9/",
        11: "VOL00010/VOL00010/DataSet_11/DataSet11_extracted/dataset11-pdfs/",
    }

    def __init__(
        self,
        dataset_num: int,
        account_name: Optional[str] = None,
        account_key: Optional[str] = None,
        container_name: str = "epstein-files",
        connection_string: Optional[str] = None,
    ):
        """
        Initialize the Azure Blob source.

        Args:
            dataset_num: Dataset number (9 or 11)
            account_name: Azure storage account name
            account_key: Azure storage account key
            container_name: Blob container name
            connection_string: Full connection string (alternative to name/key)
        """
        self.dataset_num = dataset_num
        self.container_name = container_name

        # Get credentials from params or environment
        self.account_name = account_name or os.getenv("AZURE_STORAGE_ACCOUNT", "epsteinstorage2024")
        self.account_key = account_key or os.getenv("AZURE_STORAGE_KEY")
        self.connection_string = connection_string or os.getenv("AZURE_STORAGE_CONNECTION_STRING")

        self._client = None
        self._container = None
        self._available: Optional[bool] = None
        self._prefix = self.AZURE_PREFIXES.get(dataset_num, "")

    @property
    def source_type(self) -> SourceType:
        return SourceType.AZURE_BLOB

    @property
    def is_available(self) -> bool:
        """Check if Azure storage is reachable."""
        if self._available is not None:
            return self._available

        if not self.account_key and not self.connection_string:
            logger.warning("Azure credentials not configured")
            self._available = False
            return False

        try:
            self._ensure_client()
            # Try to list one blob to verify connectivity
            blobs = self._container.list_blobs(name_starts_with=self._prefix, results_per_page=1)
            next(iter(blobs), None)
            self._available = True
        except Exception as e:
            logger.warning(f"Azure storage unavailable: {e}")
            self._available = False

        return self._available

    def _ensure_client(self):
        """Initialize Azure client if needed."""
        if self._client is not None:
            return

        try:
            from azure.storage.blob import BlobServiceClient

            if self.connection_string:
                self._client = BlobServiceClient.from_connection_string(self.connection_string)
            else:
                conn_str = (
                    f"DefaultEndpointsProtocol=https;"
                    f"AccountName={self.account_name};"
                    f"AccountKey={self.account_key};"
                    f"EndpointSuffix=core.windows.net"
                )
                self._client = BlobServiceClient.from_connection_string(conn_str)

            self._container = self._client.get_container_client(self.container_name)

        except Exception as e:
            logger.error(f"Failed to initialize Azure client: {e}")
            raise

    def list_files(self, dataset_num: int) -> Iterator[FileMetadata]:
        """List all PDFs in Azure under the dataset prefix."""
        if dataset_num != self.dataset_num:
            return

        self._ensure_client()
        prefix = self.AZURE_PREFIXES.get(dataset_num, "")

        try:
            for blob in self._container.list_blobs(name_starts_with=prefix):
                match = re.search(r"(EFTA\d{8,11})\.pdf$", blob.name, re.IGNORECASE)
                if match:
                    yield FileMetadata(
                        efta_number=match.group(1).upper(),
                        source_type=self.source_type,
                        source_path=blob.name,
                        file_size=blob.size,
                    )
        except Exception as e:
            logger.error(f"Failed to list Azure blobs: {e}")

    def _find_blob_path(self, efta_number: str) -> Optional[str]:
        """Find the blob path for an EFTA number by searching."""
        self._ensure_client()
        efta_upper = efta_number.upper()

        # Try common patterns
        patterns = [
            f"{self._prefix}{efta_upper}.pdf",
            f"{self._prefix}{efta_upper.lower()}.pdf",
        ]

        for pattern in patterns:
            try:
                blob_client = self._container.get_blob_client(pattern)
                if blob_client.exists():
                    return pattern
            except Exception:
                pass

        # Fall back to listing and searching
        try:
            for blob in self._container.list_blobs(name_starts_with=self._prefix):
                if efta_upper in blob.name.upper() and blob.name.lower().endswith('.pdf'):
                    return blob.name
        except Exception:
            pass

        return None

    def download_file(self, metadata: FileMetadata) -> DownloadResult:
        """
        Download a single file from Azure Blob Storage.

        Args:
            metadata: File metadata (source_path should be blob name)

        Returns:
            DownloadResult with PDF data or error
        """
        start = time.time()
        efta = metadata.efta_number.upper()

        try:
            self._ensure_client()

            # Get blob path
            blob_path = metadata.source_path
            if not blob_path or not blob_path.endswith('.pdf'):
                blob_path = self._find_blob_path(efta)

            if not blob_path:
                return DownloadResult(
                    efta_number=efta,
                    success=False,
                    error_message="blob_not_found",
                    source_type=self.source_type,
                    download_time_ms=int((time.time() - start) * 1000),
                )

            # Download blob
            blob_client = self._container.get_blob_client(blob_path)
            data = blob_client.download_blob().readall()

            # Validate PDF
            is_valid, error = self.validate_pdf(data)
            if not is_valid:
                return DownloadResult(
                    efta_number=efta,
                    success=False,
                    error_message=error,
                    source_type=self.source_type,
                    download_time_ms=int((time.time() - start) * 1000),
                )

            return DownloadResult(
                efta_number=efta,
                success=True,
                data=data,
                source_type=self.source_type,
                download_time_ms=int((time.time() - start) * 1000),
                file_size=len(data),
            )

        except Exception as e:
            return DownloadResult(
                efta_number=efta,
                success=False,
                error_message=f"{type(e).__name__}: {str(e)[:80]}",
                source_type=self.source_type,
                download_time_ms=int((time.time() - start) * 1000),
            )

    def download_batch(self, metadata_list: List[FileMetadata]) -> Iterator[DownloadResult]:
        """
        Download batch from Azure.

        For Azure, each blob is independent so we just iterate.
        Could be parallelized with ThreadPoolExecutor if needed.
        """
        for metadata in metadata_list:
            yield self.download_file(metadata)
