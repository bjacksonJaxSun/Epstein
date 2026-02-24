"""
DOJ Direct Download Source Handler.

Downloads PDFs directly from the DOJ website (justice.gov). This is the
last resort (Priority 3) source due to rate limiting and slower speeds.

Use sparingly - the DOJ website should only be used when other sources fail.
"""

import os
import re
import time
import threading
from typing import Iterator, List, Optional
from urllib.parse import quote, unquote
from loguru import logger

from .base import DataSource, SourceType, FileMetadata, DownloadResult


class DojDirectSource(DataSource):
    """
    Download directly from DOJ website.

    IMPORTANT: Use as last resort only. The DOJ website:
    - Is rate-limited (1 request per second recommended)
    - May block excessive requests
    - Is slower than mirror sources

    This source includes built-in rate limiting to be respectful.
    """

    DOJ_BASE = "https://www.justice.gov/epstein/files"

    # URL patterns for different datasets
    DOJ_PATTERNS = {
        9: "https://www.justice.gov/epstein/files/DataSet%209/{efta}.pdf",
        11: "https://www.justice.gov/epstein/files/DataSet%2011/{efta}.pdf",
    }

    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        timeout: int = 60,
        max_retries: int = 2,
        user_agent: str = "Mozilla/5.0 (compatible; research-bot)",
    ):
        """
        Initialize the DOJ direct source.

        Args:
            rate_limit_delay: Minimum seconds between requests
            timeout: Request timeout in seconds
            max_retries: Number of retries on failure
            user_agent: User-Agent header value
        """
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent

        self._last_request_time = 0.0
        self._lock = threading.Lock()
        self._available: Optional[bool] = None
        self._session = None

    @property
    def source_type(self) -> SourceType:
        return SourceType.DOJ_DIRECT

    @property
    def is_available(self) -> bool:
        """Check if the DOJ website is reachable."""
        if self._available is not None:
            return self._available

        try:
            import requests

            resp = requests.head(
                self.DOJ_BASE,
                timeout=10,
                headers={"User-Agent": self.user_agent},
                allow_redirects=True,
            )
            self._available = resp.status_code in (200, 301, 302, 403)  # 403 on directory is OK
        except Exception as e:
            logger.warning(f"DOJ website unavailable: {e}")
            self._available = False

        return self._available

    def _get_session(self):
        """Get or create a requests session."""
        if self._session is None:
            import requests
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": self.user_agent,
                "Accept": "application/pdf,*/*",
            })
        return self._session

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - elapsed
                time.sleep(sleep_time)
            self._last_request_time = time.time()

    def _build_url(self, efta_number: str, doj_url: Optional[str] = None, dataset_num: Optional[int] = None) -> str:
        """
        Build the DOJ URL for an EFTA number.

        Args:
            efta_number: EFTA identifier
            doj_url: Pre-computed DOJ URL (from catalog)
            dataset_num: Dataset number for URL pattern

        Returns:
            Full DOJ URL
        """
        if doj_url:
            return doj_url

        # Try to extract dataset from EFTA range (rough heuristic)
        if dataset_num is None:
            # Default to dataset 11 for newer EFTAs
            efta_num = int(re.search(r'\d+', efta_number).group())
            dataset_num = 11 if efta_num > 500000 else 9

        pattern = self.DOJ_PATTERNS.get(dataset_num)
        if pattern:
            return pattern.format(efta=efta_number)

        # Fallback
        return f"{self.DOJ_BASE}/DataSet%20{dataset_num}/{efta_number}.pdf"

    def download_file(self, metadata: FileMetadata) -> DownloadResult:
        """
        Download a single file from the DOJ website.

        Args:
            metadata: File metadata (doj_url should contain the full URL)

        Returns:
            DownloadResult with PDF data or error
        """
        start = time.time()
        efta = metadata.efta_number.upper()

        # Get URL
        url = metadata.doj_url or metadata.source_path
        if not url or not url.startswith("http"):
            url = self._build_url(efta, metadata.doj_url)

        # Rate limit
        self._rate_limit()

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                session = self._get_session()
                response = session.get(url, timeout=self.timeout, allow_redirects=True)

                if response.status_code == 200:
                    data = response.content

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

                elif response.status_code == 404:
                    return DownloadResult(
                        efta_number=efta,
                        success=False,
                        error_message="doj_404_not_found",
                        source_type=self.source_type,
                        download_time_ms=int((time.time() - start) * 1000),
                    )

                elif response.status_code == 429:
                    # Rate limited - wait longer
                    logger.warning(f"DOJ rate limited, waiting 30s...")
                    time.sleep(30)
                    last_error = "doj_rate_limited"

                elif response.status_code == 403:
                    return DownloadResult(
                        efta_number=efta,
                        success=False,
                        error_message="doj_403_forbidden",
                        source_type=self.source_type,
                        download_time_ms=int((time.time() - start) * 1000),
                    )

                else:
                    last_error = f"http_{response.status_code}"
                    if attempt < self.max_retries:
                        time.sleep(self.rate_limit_delay * 2)

            except Exception as e:
                last_error = f"{type(e).__name__}: {str(e)[:60]}"
                if attempt < self.max_retries:
                    time.sleep(self.rate_limit_delay * 2)

        return DownloadResult(
            efta_number=efta,
            success=False,
            error_message=last_error,
            source_type=self.source_type,
            download_time_ms=int((time.time() - start) * 1000),
        )

    def download_batch(self, metadata_list: List[FileMetadata]) -> Iterator[DownloadResult]:
        """
        Download batch from DOJ.

        Downloads sequentially with rate limiting to be respectful
        to the DOJ servers.
        """
        for metadata in metadata_list:
            yield self.download_file(metadata)
