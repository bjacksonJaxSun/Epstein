"""
Download missing Dataset 9 PDFs from DOJ website.
Searches page listings to find and download specific missing EFTAs.
"""
import asyncio
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# Configuration - Use local paths to avoid network share issues with Playwright
SCRIPT_DIR = Path(__file__).parent
MISSING_EFTAS_FILE = SCRIPT_DIR / "missing_ds9_eftas.txt"
OUTPUT_DIR = Path("C:/temp/downloaded_ds9_pdfs")  # Local path for downloads
BASE_URL = "https://www.justice.gov/epstein/doj-disclosures/data-set-9-files"
DOWNLOAD_BASE = "https://www.justice.gov/epstein/files/DataSet%209/"
PROGRESS_FILE = SCRIPT_DIR / "ds9_download_progress.txt"
PAGE_PROGRESS_FILE = SCRIPT_DIR / "ds9_page_progress.txt"

# Start page - calculated based on first missing EFTA
# EFTA00068974 appears around page 25 based on user hint
# Each page has ~10 files, so we can estimate page from EFTA number
START_PAGE = 25  # Start where EFTA00068974 should be
MAX_PAGE = 10000  # Upper limit
FILES_PER_PAGE = 10  # Approximate files per page

# Timeout settings (extended for age verification)
AGE_BUTTON_TIMEOUT = 120000  # 120 seconds - plenty of time to manually click
PAGE_TIMEOUT = 30000
DOWNLOAD_TIMEOUT = 60000


def load_missing_eftas():
    """Load list of missing EFTA numbers"""
    eftas = set()
    with open(MISSING_EFTAS_FILE, 'r') as f:
        for line in f:
            efta = line.strip()
            if efta and efta.startswith('EFTA'):
                eftas.add(efta)
    return eftas


def load_completed():
    """Load list of already downloaded EFTAs"""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return set(line.strip() for line in f if line.strip())
    return set()


def save_completed(efta):
    """Mark EFTA as downloaded"""
    with open(PROGRESS_FILE, 'a') as f:
        f.write(f"{efta}\n")


def load_last_page():
    """Load last scraped page number"""
    if os.path.exists(PAGE_PROGRESS_FILE):
        with open(PAGE_PROGRESS_FILE, 'r') as f:
            try:
                return int(f.read().strip())
            except:
                pass
    return START_PAGE


def save_last_page(page_num):
    """Save last scraped page number"""
    with open(PAGE_PROGRESS_FILE, 'w') as f:
        f.write(str(page_num))


async def do_age_verification(page):
    """Handle age verification with extended timeout for manual click"""
    print("\n[AGE VERIFICATION]")
    print("  Navigating to Dataset 9 page...")

    # Use domcontentloaded instead of load, and retry with longer timeout
    for attempt in range(3):
        try:
            await page.goto(BASE_URL + "?page=25", timeout=PAGE_TIMEOUT * 2, wait_until="domcontentloaded")
            break
        except Exception as e:
            print(f"  Attempt {attempt + 1} failed: {str(e)[:50]}")
            if attempt < 2:
                await page.wait_for_timeout(3000)
            else:
                raise

    print("  Waiting for page to load...")
    await page.wait_for_timeout(5000)

    # Try auto-clicking age button
    clicked = False
    selectors = [
        '#age-button-yes',
        'button:has-text("I am 18")',
        'a:has-text("I am 18")',
        'input[value*="18"]',
        '.age-gate-yes',
        '[data-age-gate="yes"]'
    ]

    for selector in selectors:
        try:
            btn = page.locator(selector)
            if await btn.is_visible(timeout=2000):
                await btn.click()
                print(f"  Auto-clicked age button: {selector}")
                clicked = True
                await page.wait_for_timeout(3000)
                break
        except:
            continue

    if not clicked:
        print("\n" + "=" * 60)
        print("  MANUAL ACTION REQUIRED!")
        print("  Please click 'I am 18' button in the browser window.")
        print("  Waiting up to 2 minutes...")
        print("=" * 60 + "\n")

        # Wait for navigation or timeout
        try:
            # Wait for the page content to change (indicates button was clicked)
            await page.wait_for_selector('a[href*="DataSet%209"][href*=".pdf"]', timeout=AGE_BUTTON_TIMEOUT)
            print("  Age verification completed (detected PDF links).")
        except PlaywrightTimeout:
            print("  Timeout waiting for verification. Continuing anyway...")

    await page.wait_for_timeout(2000)
    print("  Ready to scrape.\n")


async def get_page_files(page, page_num):
    """Get all EFTA filenames from a page"""
    url = f"{BASE_URL}?page={page_num}"

    try:
        await page.goto(url, timeout=PAGE_TIMEOUT, wait_until="domcontentloaded")
        await page.wait_for_timeout(1000)

        # Find PDF links
        links = await page.locator('a[href*="DataSet%209"][href*=".pdf"], a[href*="DataSet 9"][href*=".pdf"]').all()

        files = []
        for link in links:
            href = await link.get_attribute('href')
            if href and '.pdf' in href:
                # Extract EFTA number from filename
                filename = href.split('/')[-1].replace('%20', ' ')
                if 'EFTA' in filename:
                    efta = filename.replace('.pdf', '').strip()
                    files.append((efta, href))
        return files

    except Exception as e:
        return []


async def download_file(page, efta, url, download_dir):
    """Download a single PDF file"""
    filepath = os.path.join(download_dir, f"{efta}.pdf")

    if os.path.exists(filepath):
        return True, "exists"

    try:
        async with page.expect_download(timeout=DOWNLOAD_TIMEOUT) as download_info:
            await page.goto(url, timeout=PAGE_TIMEOUT)

        download = await download_info.value
        await download.save_as(filepath)
        return True, "downloaded"

    except Exception as e:
        return False, str(e)[:50]


def estimate_page_for_efta(efta):
    """
    Estimate which page an EFTA might be on.
    Based on observation: EFTA00068974 is around page 25
    """
    try:
        efta_num = int(efta.replace('EFTA', ''))
        # EFTA00068974 / 68974 = about 2700 files per page-group
        # Page 25 has EFTA starting around 68000
        # So roughly: page = (efta_num - 40000) / 1100
        estimated_page = max(0, (efta_num - 40000) // 1100)
        return estimated_page
    except:
        return START_PAGE


async def main():
    print("=" * 70)
    print("Dataset 9 - Missing PDFs Downloader")
    print("=" * 70)

    # Load missing EFTAs
    missing_eftas = load_missing_eftas()
    completed = load_completed()
    still_needed = missing_eftas - completed

    print(f"\nTotal missing EFTAs: {len(missing_eftas)}")
    print(f"Already downloaded: {len(completed)}")
    print(f"Still needed: {len(still_needed)}")

    if not still_needed:
        print("\nAll files already downloaded!")
        return

    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Calculate starting page based on first missing EFTA
    saved_page = load_last_page()
    first_missing = min(still_needed)
    estimated_start = estimate_page_for_efta(first_missing)

    # Use saved progress if it's further along, otherwise use estimate
    start_page = max(saved_page, estimated_start - 5)  # Start a few pages early

    print(f"\nFirst missing EFTA: {first_missing}")
    print(f"Estimated starting page: {estimated_start}")
    print(f"Starting from page: {start_page}")
    print(f"Output directory: {OUTPUT_DIR}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            accept_downloads=True,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        # Handle age verification
        await do_age_verification(page)

        # Scrape pages looking for missing EFTAs
        found_count = 0
        downloaded_count = 0
        consecutive_empty = 0
        page_num = start_page

        print(f"\nSearching pages for {len(still_needed)} missing EFTAs...\n")

        while page_num < MAX_PAGE and still_needed:
            files = await get_page_files(page, page_num)

            if not files:
                consecutive_empty += 1
                if consecutive_empty >= 50:
                    print(f"\n[Page {page_num}] 50 consecutive empty pages - stopping")
                    break
            else:
                consecutive_empty = 0

                # Check for needed files
                for efta, url in files:
                    if efta in still_needed:
                        print(f"[Page {page_num}] Found {efta}! Downloading...", end=" ")

                        success, msg = await download_file(page, efta, url, OUTPUT_DIR)

                        if success:
                            save_completed(efta)
                            still_needed.remove(efta)
                            downloaded_count += 1
                            print(f"OK ({msg})")
                        else:
                            print(f"FAILED ({msg})")

                        found_count += 1
                        await page.wait_for_timeout(500)

            # Progress update
            if page_num % 50 == 0:
                print(f"[Page {page_num}] Scanned - Found: {found_count}, Downloaded: {downloaded_count}, Remaining: {len(still_needed)}")
                save_last_page(page_num)

            page_num += 1

            # Re-verify age periodically
            if page_num % 500 == 0:
                print("\n  [Periodic age re-verification...]")
                await do_age_verification(page)

        await browser.close()

    save_last_page(page_num)

    print(f"\n{'=' * 70}")
    print(f"SCRAPING COMPLETE")
    print(f"{'=' * 70}")
    print(f"Pages scanned: {page_num - start_page}")
    print(f"Missing EFTAs found: {found_count}")
    print(f"Successfully downloaded: {downloaded_count}")
    print(f"Still missing: {len(still_needed)}")
    print(f"Files saved to: {OUTPUT_DIR}")
    print(f"{'=' * 70}")

    if still_needed:
        print(f"\nRemaining missing EFTAs:")
        for efta in sorted(still_needed)[:20]:
            print(f"  {efta}")
        if len(still_needed) > 20:
            print(f"  ... and {len(still_needed) - 20} more")


if __name__ == "__main__":
    asyncio.run(main())
