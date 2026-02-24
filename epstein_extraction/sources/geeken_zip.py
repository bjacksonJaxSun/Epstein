"""
GeekenDev Mirror Source Handler.

Downloads PDFs from the GeekenDev mirror using HTTP range requests,
allowing efficient extraction of individual files from remote zip archives
without downloading the entire archive.

This is the preferred (Priority 1) source due to its speed.
"""

import os
import re
import time
from typing import Iterator, List, Optional, Dict
from loguru import logger

from .base import DataSource, SourceType, FileMetadata, DownloadResult


class GeekenZipSource(DataSource):
    """
    Download from GeekenDev mirror using HTTP range requests.

    Uses the remotezip library to access files within remote zip archives
    without downloading the entire archive. This is very efficient for
    selective file downloads.
    """

    ZIP_URLS = {
        9: "https://doj-files.geeken.dev/doj_zips/original_archives/DataSet%209.zip",
        11: "https://doj-files.geeken.dev/doj_zips/original_archives/DataSet%2011.zip",
    }

    def __init__(
        self,
        dataset_num: int,
        retry_count: int = 3,
        retry_delay: float = 2.0,
    ):
        """
        Initialize the GeekenDev zip source.

        Args:
            dataset_num: Dataset number (9 or 11)
            retry_count: Number of retries on failure
            retry_delay: Seconds to wait between retries
        """
        self.dataset_num = dataset_num
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self._zip_url = self.ZIP_URLS.get(dataset_num)
        self._zip_index: Optional[Dict[str, str]] = None  # efta -> zip_path
        self._available: Optional[bool] = None
        self._rz = None  # RemoteZip instance (lazy loaded)

    @property
    def source_type(self) -> SourceType:
        return SourceType.GEEKEN_ZIP

    @property
    def is_available(self) -> bool:
        """Check if the GeekenDev mirror is reachable."""
        if self._available is not None:
            return self._available

        if not self._zip_url:
            self._available = False
            return False

        try:
            import requests
            resp = requests.head(self._zip_url, timeout=10, allow_redirects=True)
            # 200 = OK, 206 = Partial Content (range requests supported)
            self._available = resp.status_code in (200, 206)
        except Exception as e:
            logger.warning(f"GeekenDev mirror unavailable: {e}")
            self._available = False

        return self._available

    def _ensure_index(self):
        """Build the zip file index if not already done."""
        if self._zip_index is not None:
            return

        if not self._zip_url:
            self._zip_index = {}
            return

        try:
            from remotezip import RemoteZip

            logger.info(f"Building index for {self._zip_url}...")
            self._zip_index = {}

            with RemoteZip(self._zip_url) as rz:
                for name in rz.namelist():
                    match = re.search(r"(EFTA\d{8,11})\.pdf$", name, re.IGNORECASE)
                    if match:
                        efta = match.group(1).upper()
                        self._zip_index[efta] = name

            logger.info(f"Indexed {len(self._zip_index)} PDFs from GeekenDev mirror")

        except Exception as e:
            logger.error(f"Failed to build GeekenDev index: {e}")
            self._zip_index = {}

    def get_zip_path(self, efta_number: str) -> Optional[str]:
        """Get the path within the zip for an EFTA number."""
        self._ensure_index()
        return self._zip_index.get(efta_number.upper())

    def list_files(self, dataset_num: int) -> Iterator[FileMetadata]:
        """List all PDFs available in the remote zip."""
        if dataset_num != self.dataset_num:
            return

        self._ensure_index()

        for efta, zip_path in self._zip_index.items():
            yield FileMetadata(
                efta_number=efta,
                source_type=self.source_type,
                source_path=zip_path,
            )

    def download_file(self, metadata: FileMetadata) -> DownloadResult:
        """
        Download a single file from the remote zip.

        Args:
            metadata: File metadata (source_path should be zip entry path or EFTA)

        Returns:
            DownloadResult with PDF data or error
        """
        start = time.time()
        efta = metadata.efta_number.upper()

        if not self._zip_url:
            return DownloadResult(
                efta_number=efta,
                success=False,
                error_message=f"no_zip_url_for_dataset_{self.dataset_num}",
                source_type=self.source_type,
                download_time_ms=int((time.time() - start) * 1000),
            )

        # Get zip path - either from metadata or lookup
        zip_path = metadata.source_path
        if not zip_path or not zip_path.endswith('.pdf'):
            zip_path = self.get_zip_path(efta)

        if not zip_path:
            return DownloadResult(
                efta_number=efta,
                success=False,
                error_message="not_in_zip_index",
                source_type=self.source_type,
                download_time_ms=int((time.time() - start) * 1000),
            )

        # Try downloading with retries
        last_error = None
        for attempt in range(self.retry_count):
            try:
                from remotezip import RemoteZip

                with RemoteZip(self._zip_url) as rz:
                    data = rz.read(zip_path)

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
                last_error = f"{type(e).__name__}: {str(e)[:80]}"
                if attempt < self.retry_count - 1:
                    logger.debug(f"Retry {attempt + 1} for {efta}: {last_error}")
                    time.sleep(self.retry_delay)

        return DownloadResult(
            efta_number=efta,
            success=False,
            error_message=last_error,
            source_type=self.source_type,
            download_time_ms=int((time.time() - start) * 1000),
        )

    def download_batch(self, metadata_list: List[FileMetadata]) -> Iterator[DownloadResult]:
        """
        Download batch using a single RemoteZip connection for efficiency.

        Keeps the connection open across multiple file reads to reduce
        overhead from repeated HTTP handshakes.
        """
        if not self._zip_url or not metadata_list:
            return

        self._ensure_index()

        try:
            from remotezip import RemoteZip

            with RemoteZip(self._zip_url) as rz:
                for metadata in metadata_list:
                    start = time.time()
                    efta = metadata.efta_number.upper()

                    # Get zip path
                    zip_path = metadata.source_path
                    if not zip_path or not zip_path.endswith('.pdf'):
                        zip_path = self._zip_index.get(efta)

                    if not zip_path:
                        yield DownloadResult(
                            efta_number=efta,
                            success=False,
                            error_message="not_in_zip_index",
                            source_type=self.source_type,
                            download_time_ms=int((time.time() - start) * 1000),
                        )
                        continue

                    try:
                        data = rz.read(zip_path)

                        is_valid, error = self.validate_pdf(data)
                        if not is_valid:
                            yield DownloadResult(
                                efta_number=efta,
                                success=False,
                                error_message=error,
                                source_type=self.source_type,
                                download_time_ms=int((time.time() - start) * 1000),
                            )
                        else:
                            yield DownloadResult(
                                efta_number=efta,
                                success=True,
                                data=data,
                                source_type=self.source_type,
                                download_time_ms=int((time.time() - start) * 1000),
                                file_size=len(data),
                            )

                    except Exception as e:
                        yield DownloadResult(
                            efta_number=efta,
                            success=False,
                            error_message=f"{type(e).__name__}: {str(e)[:80]}",
                            source_type=self.source_type,
                            download_time_ms=int((time.time() - start) * 1000),
                        )

        except Exception as e:
            logger.error(f"Batch download failed: {e}")
            # Return error for all remaining items
            for metadata in metadata_list:
                yield DownloadResult(
                    efta_number=metadata.efta_number,
                    success=False,
                    error_message=f"batch_failed: {type(e).__name__}",
                    source_type=self.source_type,
                )
