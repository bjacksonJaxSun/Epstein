#!/usr/bin/env python3
"""
Headless downloader for Epstein files from Justice.gov - Dataset 1.
Handles age verification, pagination wrapping, and session expiration.
"""

import asyncio
import os
import json
import time
import aiohttp
import aiofiles
from pathlib import Path
from loguru import logger
from playwright.async_api import async_playwright

# Configuration
DATASET_NUM = 1
BASE_URL = "https://www.justice.gov/epstein/doj-disclosures/data-set-1-files"
DOWNLOAD_BASE = "https://www.justice.gov/epstein/files/DataSet%201/"

OUTPUT_DIR = "/data/downloaded_pdfs/DataSet_1"
PROGRESS_FILE = "/data/epstein_extraction/download_ds1_progress.json"
DOWNLOAD_DELAY = 0.3  # seconds between downloads
MAX_RETRIES = 3
SESSION_TIMEOUT = 300  # Re-verify age every 5 minutes


class EpsteinDownloader:
    def __init__(self):
        self.browser = None
        self.page = None
        self.cookies = {}
        self.session_start = 0
        self.progress = {"last_page": -1, "files_scraped": [], "downloaded": 0, "errors": 0}

    def load_progress(self):
        if os.path.exists(PROGRESS_FILE):
            try:
                with open(PROGRESS_FILE, 'r') as f:
                    self.progress = json.load(f)
                logger.info(f"Loaded progress: page {self.progress['last_page']}, {len(self.progress['files_scraped'])} files")
            except:
                pass

    def save_progress(self):
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(self.progress, f)

    async def start(self):
        """Initialize browser and perform age verification."""
        logger.info("Starting headless browser...")

        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True)
        self.page = await self.browser.new_page()

        await self.do_age_verification()

    async def do_age_verification(self):
        """Handle age verification."""
        logger.info("Performing age verification...")

        await self.page.goto("https://www.justice.gov/age-verify")
        await self.page.wait_for_timeout(3000)

        # Click "I am not a robot" button
        try:
            robot_btn = self.page.locator('input[value="I am not a robot"]')
            if await robot_btn.is_visible(timeout=2000):
                await robot_btn.click()
                logger.info("Clicked 'I am not a robot' button")
                await self.page.wait_for_timeout(3000)
        except Exception as e:
            logger.debug(f"Robot button not found: {e}")

        # Click "Yes" (18+) button
        try:
            age_btn = self.page.locator('#age-button-yes')
            if await age_btn.is_visible(timeout=2000):
                await age_btn.click()
                logger.info("Clicked age verification button")
                await self.page.wait_for_timeout(3000)
        except Exception as e:
            logger.warning(f"Age button not found: {e}")
            raise Exception("Failed to complete age verification")

        # Extract cookies
        cookies = await self.page.context.cookies()
        self.cookies = {c['name']: c['value'] for c in cookies}
        self.session_start = time.time()

        logger.info(f"Age verification complete. Got {len(self.cookies)} cookies.")

    async def check_session(self):
        """Re-verify if session is old."""
        if time.time() - self.session_start > SESSION_TIMEOUT:
            logger.info("Session timeout - re-verifying age...")
            await self.do_age_verification()

    async def get_page_files(self, page_num):
        """Get filenames from a dataset page."""
        url = f"{BASE_URL}?page={page_num}"

        try:
            await self.page.goto(url, timeout=30000, wait_until="domcontentloaded")
            await self.page.wait_for_timeout(1000)

            # Find PDF links
            selector = f'a[href*="DataSet%201"][href*=".pdf"], a[href*="DataSet 1"][href*=".pdf"]'
            links = await self.page.locator(selector).all()

            files = []
            for link in links:
                href = await link.get_attribute('href')
                if href and href.endswith('.pdf'):
                    filename = href.split('/')[-1].replace('%20', ' ')
                    if 'EFTA' in filename:
                        files.append(filename)

            return files
        except Exception as e:
            logger.error(f"Error getting page {page_num}: {e}")
            return []

    async def find_last_page(self):
        """Binary search to find last page (detect wrapping)."""
        logger.info("Finding last page for dataset 1...")

        # Get page 0 files for wrapping detection
        page0_files = await self.get_page_files(0)
        if not page0_files:
            logger.warning("No files on page 0")
            return -1

        logger.info(f"Page 0 has {len(page0_files)} files")

        # Exponential search for upper bound
        low, high = 0, 100
        while high <= 100000:
            files = await self.get_page_files(high)

            if not files:
                # Empty page - found upper bound
                break
            elif files and page0_files and files[0] == page0_files[0]:
                # Wrapping detected
                logger.info(f"Wrapping at page {high}")
                break
            else:
                # Valid page - continue
                low = high
                high *= 2
                logger.info(f"Page {low} valid, trying {high}...")

        # Binary search
        logger.info(f"Binary search between {low} and {high}...")
        while low < high - 1:
            mid = (low + high) // 2
            files = await self.get_page_files(mid)

            if not files:
                high = mid
            elif files and page0_files and files[0] == page0_files[0]:
                high = mid
            else:
                low = mid

        logger.info(f"Last page is {low}")
        return low

    async def scrape_all_files(self):
        """Scrape all filenames from the dataset."""
        last_page = await self.find_last_page()
        if last_page < 0:
            return []

        # Resume from saved progress
        start_page = self.progress['last_page'] + 1
        all_files = self.progress['files_scraped'].copy()

        page0_files = await self.get_page_files(0)

        for page_num in range(start_page, last_page + 1):
            files = await self.get_page_files(page_num)

            # Check for wrapping
            if page_num > 0 and files and page0_files and files[0] == page0_files[0]:
                logger.info(f"Wrapping detected at page {page_num} - stopping")
                break

            all_files.extend(files)

            if page_num % 50 == 0:
                logger.info(f"Scraped {page_num}/{last_page} pages, {len(all_files)} files")
                self.progress['last_page'] = page_num
                self.progress['files_scraped'] = list(set(all_files))
                self.save_progress()

            await self.check_session()

        self.progress['files_scraped'] = list(set(all_files))
        self.save_progress()
        return list(set(all_files))  # Deduplicate

    async def download_file(self, session, url, filepath):
        """Download a single file."""
        for retry in range(MAX_RETRIES):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status == 200:
                        content = await response.read()

                        # Verify it's a PDF
                        if content[:4] == b'%PDF':
                            async with aiofiles.open(filepath, 'wb') as f:
                                await f.write(content)
                            return True
                        else:
                            # Got HTML - session expired
                            if b'age-verify' in content.lower():
                                logger.warning("Session expired - need re-verification")
                                return None  # Signal session expired
                            return False
                    elif response.status == 404:
                        return False  # File doesn't exist
                    else:
                        logger.warning(f"HTTP {response.status} for {url}")

            except Exception as e:
                logger.debug(f"Retry {retry+1}/{MAX_RETRIES}: {e}")
                await asyncio.sleep(1)

        return False

    async def download_missing(self, existing_eftas):
        """Download missing files."""
        logger.info("=" * 60)
        logger.info("Processing Dataset 1")
        logger.info("=" * 60)

        # Scrape all filenames
        all_files = await self.scrape_all_files()
        logger.info(f"Found {len(all_files)} files on website")

        # Find missing files
        missing = []
        for filename in all_files:
            efta = filename.replace('.pdf', '').replace(' ', '')
            if efta not in existing_eftas:
                missing.append(filename)

        logger.info(f"Missing files to download: {len(missing)}")

        if not missing:
            return 0

        # Create output directory
        Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

        # Download missing files
        downloaded = 0
        errors = 0

        # Create session with cookies
        jar = aiohttp.CookieJar()
        async with aiohttp.ClientSession(cookie_jar=jar) as session:
            # Set cookies
            for name, value in self.cookies.items():
                jar.update_cookies({name: value})

            for i, filename in enumerate(missing):
                url = DOWNLOAD_BASE + filename.replace(' ', '%20')
                filepath = Path(OUTPUT_DIR) / filename

                # Skip if already downloaded
                if filepath.exists():
                    continue

                result = await self.download_file(session, url, filepath)

                if result is None:
                    # Session expired - re-verify and retry
                    await self.do_age_verification()
                    for name, value in self.cookies.items():
                        jar.update_cookies({name: value})
                    result = await self.download_file(session, url, filepath)

                if result:
                    downloaded += 1
                    self.progress['downloaded'] = downloaded
                else:
                    errors += 1
                    self.progress['errors'] = errors

                if (i + 1) % 100 == 0:
                    logger.info(f"Progress: {i+1}/{len(missing)} - Downloaded: {downloaded}, Errors: {errors}")
                    self.save_progress()

                await asyncio.sleep(DOWNLOAD_DELAY)

        logger.info(f"Dataset 1 complete: Downloaded {downloaded}, Errors {errors}")
        return downloaded

    async def run(self):
        """Run the downloader."""
        self.load_progress()
        await self.start()

        # Get existing EFTA numbers from database
        logger.info("Fetching existing documents from database...")
        import psycopg2
        conn = psycopg2.connect(
            dbname="epstein_documents",
            user="epstein_user",
            password="epstein_secure_pw_2024",
            host="localhost"
        )
        cur = conn.cursor()
        cur.execute("SELECT efta_number FROM documents")
        existing_eftas = set(row[0] for row in cur.fetchall())
        cur.close()
        conn.close()
        logger.info(f"Found {len(existing_eftas)} existing documents in database")

        # Download missing files
        total_downloaded = await self.download_missing(existing_eftas)

        await self.browser.close()

        logger.info("=" * 60)
        logger.info(f"DOWNLOAD COMPLETE - Total: {total_downloaded}")
        logger.info("=" * 60)


async def main():
    logger.add("/data/epstein_extraction/downloader_ds1.log", rotation="100 MB")

    downloader = EpsteinDownloader()
    await downloader.run()


if __name__ == "__main__":
    asyncio.run(main())
