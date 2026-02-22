"""
Catalog all EFTA filenames from the DOJ Epstein disclosures website.
Does NOT download any files - just collects the filenames listed on each page.

Outputs:
  - doj_catalog.txt          : All EFTA filenames found, one per line (EFTA\tDataset\tURL)
  - doj_catalog_progress.txt : Tracks progress to allow resuming

Usage:
    python catalog_doj_files.py [--start-dataset 1] [--headless]
"""
import asyncio
import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

SCRIPT_DIR = Path(__file__).parent
CATALOG_FILE = SCRIPT_DIR / "doj_catalog.txt"
PROGRESS_FILE = SCRIPT_DIR / "doj_catalog_progress.txt"

# DOJ dataset page URLs (1-12)
DATASET_URLS = {
    1: "https://www.justice.gov/epstein/doj-disclosures/data-set-1-files",
    2: "https://www.justice.gov/epstein/doj-disclosures/data-set-2-files",
    3: "https://www.justice.gov/epstein/doj-disclosures/data-set-3-files",
    4: "https://www.justice.gov/epstein/doj-disclosures/data-set-4-files",
    5: "https://www.justice.gov/epstein/doj-disclosures/data-set-5-files",
    6: "https://www.justice.gov/epstein/doj-disclosures/data-set-6-files",
    7: "https://www.justice.gov/epstein/doj-disclosures/data-set-7-files",
    8: "https://www.justice.gov/epstein/doj-disclosures/data-set-8-files",
    9: "https://www.justice.gov/epstein/doj-disclosures/data-set-9-files",
    10: "https://www.justice.gov/epstein/doj-disclosures/data-set-10-files",
    11: "https://www.justice.gov/epstein/doj-disclosures/data-set-11-files",
    12: "https://www.justice.gov/epstein/doj-disclosures/data-set-12-files",
}

# Known last page numbers per dataset (from manual inspection of DOJ site)
# Used as hard stop so we don't rely solely on heuristic detection
KNOWN_LAST_PAGES = {
    9: 9424,
    10: 148,
    11: 6615,
    12: 3,
}

# Timeouts
AGE_BUTTON_TIMEOUT = 120000  # 2 minutes for manual click if needed
PAGE_TIMEOUT = 30000
MAX_CONSECUTIVE_EMPTY = 50  # Stop after this many truly-empty rendered pages in a row
MAX_RETRIES = 3  # Retries per page on transient errors
MAX_AGE_GATE_RETRIES = 5  # Max age gate retries per page before waiting for manual click


def load_progress():
    """Load resume state: {dataset: last_page_scraped}"""
    progress = {}
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and '\t' in line:
                    ds, page = line.split('\t')
                    progress[int(ds)] = int(page)
    return progress


def save_progress(dataset, page_num):
    """Update progress for a dataset"""
    progress = load_progress()
    progress[dataset] = page_num
    with open(PROGRESS_FILE, 'w') as f:
        for ds in sorted(progress):
            f.write(f"{ds}\t{progress[ds]}\n")


def load_existing_catalog(dataset_filter=None):
    """Load already-cataloged EFTAs to avoid duplicates.

    If dataset_filter is set, only load EFTAs from that dataset (saves memory).
    """
    existing = set()
    if CATALOG_FILE.exists():
        with open(CATALOG_FILE, 'r') as f:
            for line in f:
                if line.startswith('EFTA'):
                    parts = line.strip().split('\t')
                    efta = parts[0]
                    if dataset_filter is not None and len(parts) >= 2:
                        if parts[1] != str(dataset_filter):
                            continue
                    existing.add(efta)
    return existing


def append_to_catalog(entries):
    """Append new entries to the catalog file"""
    with open(CATALOG_FILE, 'a') as f:
        for efta, dataset, url in entries:
            f.write(f"{efta}\t{dataset}\t{url}\n")


def extract_files_from_html(html, dataset_num):
    """Extract all EFTA filenames and URLs from page HTML using regex.

    Much faster than per-element DOM queries - single pass over the HTML.
    """
    files = []
    # Match any href containing .pdf with an EFTA number
    hrefs = re.findall(r'href="([^"]*\.pdf[^"]*)"', html, re.IGNORECASE)
    seen = set()
    for href in hrefs:
        # URL decode the href for filename extraction
        decoded = unquote(href)
        match = re.search(r'(EFTA\d{8})', decoded)
        if match:
            efta = match.group(1)
            if efta in seen:
                continue
            seen.add(efta)
            # Normalize URL
            full_url = href
            if href.startswith('/'):
                full_url = 'https://www.justice.gov' + href
            files.append((efta, dataset_num, full_url))
    return files


def is_age_gate_url(url):
    """Check if the current URL indicates an age verification redirect."""
    lowered = url.lower()
    return any(kw in lowered for kw in ('age-verify', 'age_verify', 'age-gate', 'age_gate', '/age/', 'ageverif'))


async def handle_age_gate(page, target_url):
    """Handle age gate redirect. Returns True if gate was handled."""
    print("    [Age gate detected] Attempting to bypass...")

    # Try auto-clicking age verification button (covers both "Yes" and "I am 18" styles)
    selectors = [
        '#age-button-yes',
        'button:has-text("Yes")',
        'a:has-text("Yes")',
        'button:has-text("I am 18")',
        'a:has-text("I am 18")',
        'button:has-text("18 years")',
        'a:has-text("18 years")',
        'input[value*="Yes"]',
        'input[value*="18"]',
        '.age-gate-yes',
        '[data-age-gate="yes"]',
    ]

    for selector in selectors:
        try:
            btn = page.locator(selector)
            if await btn.is_visible(timeout=2000):
                await btn.click()
                print(f"      Auto-clicked: {selector}")
                await page.wait_for_timeout(3000)
                return True
        except:
            continue

    # Manual fallback
    print("\n" + "=" * 60)
    print("  MANUAL ACTION REQUIRED!")
    print("  Please click 'I am 18' button in the browser window.")
    print(f"  Target URL: {target_url}")
    print("  Waiting up to 2 minutes...")
    print("=" * 60 + "\n")

    try:
        await page.wait_for_selector('a[href*=".pdf"], .pager', timeout=AGE_BUTTON_TIMEOUT)
        print("    Age verification completed.")
        return True
    except PlaywrightTimeout:
        print("    Timeout waiting for age verification.")
        return False


async def do_age_verification(page, base_url):
    """Handle initial age verification for a dataset."""
    print("  [Age verification] Navigating...")

    for attempt in range(3):
        try:
            await page.goto(base_url + "?page=0", timeout=PAGE_TIMEOUT * 2, wait_until="domcontentloaded")
            break
        except Exception as e:
            print(f"    Attempt {attempt + 1} failed: {str(e)[:60]}")
            if attempt < 2:
                await page.wait_for_timeout(3000)
            else:
                raise

    await page.wait_for_timeout(3000)

    # Check if we were redirected to age gate
    current_url = page.url
    if is_age_gate_url(current_url):
        print(f"    Age gate URL detected: {current_url}")
        await handle_age_gate(page, base_url + "?page=0")
    else:
        # Still try the old button-check approach in case the gate is inline
        selectors = [
            '#age-button-yes',
            'button:has-text("Yes")',
            'a:has-text("Yes")',
            'button:has-text("I am 18")',
            'a:has-text("I am 18")',
            'button:has-text("18 years")',
            'a:has-text("18 years")',
        ]
        for selector in selectors:
            try:
                btn = page.locator(selector)
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    print(f"    Auto-clicked: {selector}")
                    await page.wait_for_timeout(3000)
                    return True
            except:
                continue

    # Wait for content to confirm we're past the gate
    try:
        await page.wait_for_selector('a[href*=".pdf"], .pager', timeout=10000)
        print("    Age verification OK - content visible.")
    except:
        print("    Warning: Could not confirm content is visible after age verification.")

    return True


async def scrape_page_filenames(page, url, dataset_num):
    """Extract all EFTA filenames and URLs from a single page.

    Returns: (files, page_status)
        files: list of (efta, dataset_num, url) tuples
        page_status: 'ok', 'age_gate', 'error', or 'empty'
    """
    for attempt in range(MAX_RETRIES):
        try:
            await page.goto(url, timeout=PAGE_TIMEOUT, wait_until="domcontentloaded")

            # Fix 1: Detect age gate redirect by checking URL
            if is_age_gate_url(page.url):
                handled = await handle_age_gate(page, url)
                if handled:
                    # Re-navigate to the actual target page
                    await page.goto(url, timeout=PAGE_TIMEOUT, wait_until="domcontentloaded")
                    # Check again - if still on age gate, it's stuck
                    if is_age_gate_url(page.url):
                        return [], 'age_gate'
                else:
                    return [], 'age_gate'

            # Fix 2: Wait for content to render (JS-rendered file listings)
            try:
                await page.wait_for_selector('a[href*=".pdf"], .pager, .view-empty', timeout=10000)
            except PlaywrightTimeout:
                # Could be a truly empty page or slow render - check content anyway
                pass

            # Fix 3: Extract all filenames from HTML at once (fast regex)
            html = await page.content()

            # Check for inline age gate (not caught by URL check)
            if re.search(r'18\s*years\s*of\s*age|age.?verif|are\s*you\s*18', html, re.IGNORECASE):
                if not re.search(r'EFTA\d{8}', html):
                    # Looks like an age gate page, not a data page
                    print(f"      Inline age gate detected on {url}")
                    return [], 'age_gate'

            files = extract_files_from_html(html, dataset_num)

            if files:
                return files, 'ok'
            else:
                # Confirm the page actually rendered by checking for common page elements
                has_pager = bool(re.search(r'class="pager"', html))
                has_view = bool(re.search(r'class="view-content"', html))
                if has_pager or has_view:
                    # Page rendered but has no files - genuinely empty (past last page)
                    return [], 'empty'
                else:
                    # Page didn't render properly - might be a transient issue
                    if attempt < MAX_RETRIES - 1:
                        wait = 2 ** (attempt + 1)
                        print(f"      Page didn't render, retrying in {wait}s (attempt {attempt + 1}/{MAX_RETRIES})")
                        await page.wait_for_timeout(wait * 1000)
                        continue
                    return [], 'empty'

        except PlaywrightTimeout:
            if attempt < MAX_RETRIES - 1:
                wait = 2 ** (attempt + 1)
                print(f"      Timeout, retrying in {wait}s (attempt {attempt + 1}/{MAX_RETRIES})")
                await page.wait_for_timeout(wait * 1000)
                continue
            return [], 'error'
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = 2 ** (attempt + 1)
                print(f"      Error: {str(e)[:60]}, retrying in {wait}s (attempt {attempt + 1}/{MAX_RETRIES})")
                await page.wait_for_timeout(wait * 1000)
                continue
            print(f"    Error on page: {str(e)[:60]}")
            return [], 'error'

    return [], 'error'


async def catalog_dataset(page, dataset_num, base_url, start_page, existing_eftas):
    """Catalog all files in a dataset, page by page.

    Stop conditions (in priority order):
    1. Known last page: hard stop from KNOWN_LAST_PAGES dict
    2. Wrap-around detection: DOJ site wraps past the last page back to page 0 content
    3. Consecutive empty pages: MAX_CONSECUTIVE_EMPTY truly-empty rendered pages in a row
    """
    last_page = KNOWN_LAST_PAGES.get(dataset_num)
    print(f"\n{'='*60}")
    print(f"  Dataset {dataset_num}: {base_url}")
    print(f"  Resuming from page {start_page}")
    if last_page is not None:
        print(f"  Known last page: {last_page}")
    print(f"{'='*60}")

    total_found = 0
    new_found = 0
    consecutive_empty = 0
    consecutive_errors = 0
    age_gate_retries = 0  # Track retries for age gate on same page
    first_page_efta = None  # First EFTA on the start page, used for wrap-around detection
    page_num = start_page

    while True:
        # Hard stop: known last page
        if last_page is not None and page_num > last_page:
            print(f"  Reached known last page ({last_page}) - dataset complete")
            break

        url = f"{base_url}?page={page_num}"
        files, status = await scrape_page_filenames(page, url, dataset_num)

        if status == 'age_gate':
            age_gate_retries += 1
            if age_gate_retries <= MAX_AGE_GATE_RETRIES:
                print(f"  [Page {page_num}] Age gate detected (attempt {age_gate_retries}/{MAX_AGE_GATE_RETRIES}) - trying to handle...")
                # Try clicking the button on the CURRENT page (don't navigate away)
                await handle_age_gate(page, url)
                # Don't increment page_num - retry this page
                continue
            else:
                # Too many retries - wait for manual intervention
                print(f"\n{'!'*60}")
                print(f"  Age gate stuck on page {page_num} after {MAX_AGE_GATE_RETRIES} retries.")
                print(f"  Please manually click the age verification button in the browser.")
                print(f"  The script will continue automatically once content is visible.")
                print(f"{'!'*60}\n")
                try:
                    await page.wait_for_selector('a[href*=".pdf"], .pager', timeout=AGE_BUTTON_TIMEOUT)
                    print("    Manual age verification completed - resuming.")
                    age_gate_retries = 0
                except PlaywrightTimeout:
                    print("    Timeout waiting for manual intervention - skipping page.")
                    age_gate_retries = 0
                    # Fall through to advance page_num
        elif status == 'error':
            age_gate_retries = 0
            consecutive_errors += 1
            # Don't count network errors as empty pages
            if consecutive_errors >= 5:
                print(f"  [Page {page_num}] {consecutive_errors} consecutive errors - pausing 10s")
                await page.wait_for_timeout(10000)
                consecutive_errors = 0
            # Still advance to next page
        elif status == 'empty':
            age_gate_retries = 0
            consecutive_empty += 1
            consecutive_errors = 0
            if last_page is None and consecutive_empty >= MAX_CONSECUTIVE_EMPTY:
                print(f"  [Page {page_num}] {MAX_CONSECUTIVE_EMPTY} consecutive empty pages - dataset complete")
                break
        elif status == 'ok':
            age_gate_retries = 0
            consecutive_empty = 0
            consecutive_errors = 0

            # Wrap-around detection: DOJ wraps past last page back to page 0
            if files:
                page_first_efta = files[0][0]  # first EFTA on this page
                if first_page_efta is None:
                    first_page_efta = page_first_efta
                elif page_first_efta == first_page_efta and page_num != start_page:
                    print(f"  [Page {page_num}] Wrap-around detected (saw {first_page_efta} again) - dataset complete")
                    break

            total_found += len(files)

            # Filter out already-cataloged entries
            new_entries = [(e, d, u) for e, d, u in files if e not in existing_eftas]
            if new_entries:
                append_to_catalog(new_entries)
                new_found += len(new_entries)
                for efta, _, _ in new_entries:
                    existing_eftas.add(efta)

        # Progress update
        if page_num % 25 == 0:
            progress_info = f"/{last_page}" if last_page else ""
            print(f"  [Page {page_num}{progress_info}] Total: {total_found}, New: {new_found}, Empty streak: {consecutive_empty}")
            save_progress(dataset_num, page_num)

        page_num += 1

    save_progress(dataset_num, page_num)
    print(f"  Dataset {dataset_num} complete: {total_found} files found ({new_found} new)")
    return total_found, new_found


async def main():
    parser = argparse.ArgumentParser(description="Catalog DOJ Epstein disclosure filenames")
    parser.add_argument("--start-dataset", type=int, default=1, help="Dataset to start from (default: 1)")
    parser.add_argument("--end-dataset", type=int, default=12, help="Dataset to end at (default: 12)")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    args = parser.parse_args()

    print("=" * 60)
    print("DOJ Epstein Disclosures - Filename Catalog")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Datasets: {args.start_dataset} through {args.end_dataset}")
    print(f"Catalog file: {CATALOG_FILE}")
    print("=" * 60)

    # Load existing state
    progress = load_progress()
    # When cataloging a single dataset, only load that dataset's EFTAs (saves memory)
    ds_filter = args.start_dataset if args.start_dataset == args.end_dataset else None
    existing_eftas = load_existing_catalog(dataset_filter=ds_filter)
    filter_msg = f" (dataset {ds_filter} only)" if ds_filter else ""
    print(f"Already cataloged: {len(existing_eftas)} EFTAs{filter_msg}")

    grand_total = 0
    grand_new = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=args.headless,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        for ds_num in range(args.start_dataset, args.end_dataset + 1):
            if ds_num not in DATASET_URLS:
                print(f"\nSkipping Dataset {ds_num} - no URL configured")
                continue

            base_url = DATASET_URLS[ds_num]
            start_page = progress.get(ds_num, 0)

            # Age verification for each dataset
            await do_age_verification(page, base_url)

            total, new = await catalog_dataset(page, ds_num, base_url, start_page, existing_eftas)
            grand_total += total
            grand_new += new

        await browser.close()

    # Final summary
    print(f"\n{'='*60}")
    print(f"CATALOGING COMPLETE")
    print(f"{'='*60}")
    print(f"Total files seen across pages: {grand_total}")
    print(f"New EFTAs added to catalog: {grand_new}")
    print(f"Total unique EFTAs in catalog: {len(existing_eftas)}")
    print(f"Catalog saved to: {CATALOG_FILE}")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
