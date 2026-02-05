"""
Resume scraping Dataset 10 from page 1400 through 3299.
The initial scrape stopped at page 1396 due to 20 consecutive empty pages.
Binary search confirmed content exists up to page 3299.
This script skips the empty gap and continues scraping.
"""
import asyncio
import json
import os
from playwright.async_api import async_playwright

OUTPUT_DIR = "epstein_files/DataSet_10"
BASE_URL = "https://www.justice.gov/epstein/doj-disclosures/data-set-10-files"
DOWNLOAD_BASE = "https://www.justice.gov/epstein/files/DataSet%2010/"

START_PAGE = 1400
END_PAGE = 3299

async def get_page_files(page, page_num):
    """Get all filenames from a page"""
    url = f"{BASE_URL}?page={page_num}"
    try:
        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        await page.wait_for_timeout(1000)

        links = await page.locator('a[href*="DataSet%2010"][href*=".pdf"], a[href*="DataSet 10"][href*=".pdf"]').all()

        files = []
        for link in links:
            href = await link.get_attribute('href')
            if href and href.endswith('.pdf'):
                filename = href.split('/')[-1].replace('%20', ' ')
                if 'EFTA' in filename:
                    files.append(filename)
        return files
    except Exception as e:
        print(f"  [{page_num}] Error: {e}")
        return []

async def do_age_verification(page):
    """Handle age verification"""
    print("Navigating to Dataset 10 page...")
    await page.goto(BASE_URL)
    await page.wait_for_timeout(3000)

    try:
        robot = page.locator('input[value="I am not a robot"]')
        if await robot.is_visible(timeout=2000):
            await robot.click()
            await page.wait_for_timeout(3000)
            print("  Clicked robot button")
    except:
        pass

    try:
        age = page.locator('#age-button-yes')
        if await age.is_visible(timeout=2000):
            await age.click()
            await page.wait_for_timeout(3000)
            print("  Clicked age button")
    except:
        pass

async def main():
    print("=" * 70)
    print("Dataset 10 - Resume Scraper (pages 1400-3299)")
    print("=" * 70)

    # Load existing files
    existing_file = os.path.join(OUTPUT_DIR, "actual_filenames.txt")
    existing_files = set()
    if os.path.exists(existing_file):
        with open(existing_file, 'r') as f:
            existing_files = set(line.strip() for line in f if line.strip())
        print(f"Loaded {len(existing_files)} existing files")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        await do_age_verification(page)

        print(f"\nScraping pages {START_PAGE} through {END_PAGE}...\n")

        new_files = []
        consecutive_empty = 0
        pages_with_content = 0

        for page_num in range(START_PAGE, END_PAGE + 1):
            files = await get_page_files(page, page_num)

            if len(files) == 0:
                consecutive_empty += 1
                # Don't stop - just track gaps
            else:
                if consecutive_empty > 0:
                    print(f"  [{page_num}] Found content after {consecutive_empty} empty pages")
                consecutive_empty = 0
                pages_with_content += 1
                new_files.extend(files)

            if page_num % 10 == 0:
                pct = ((page_num - START_PAGE) / (END_PAGE - START_PAGE + 1)) * 100
                print(f"  [{page_num}/{END_PAGE}] {pct:.1f}% - {len(new_files)} new files (empty streak: {consecutive_empty})")

        await browser.close()

    # Deduplicate new files
    new_unique = set(new_files) - existing_files
    print(f"\n{'=' * 70}")
    print(f"RESUME SCRAPING COMPLETE")
    print(f"{'=' * 70}")
    print(f"Pages with content: {pages_with_content}")
    print(f"New files collected: {len(new_files)}")
    print(f"New unique files (not in existing): {len(new_unique)}")

    if new_unique:
        # Merge with existing
        all_files = sorted(existing_files | new_unique)
        print(f"Total unique files after merge: {len(all_files)}")

        with open(os.path.join(OUTPUT_DIR, "actual_filenames.json"), 'w') as f:
            json.dump(list(all_files), f, indent=2)

        with open(os.path.join(OUTPUT_DIR, "actual_filenames.txt"), 'w') as f:
            for fn in all_files:
                f.write(f"{fn}\n")

        with open(os.path.join(OUTPUT_DIR, "actual_download_urls.txt"), 'w') as f:
            for fn in all_files:
                f.write(f"{DOWNLOAD_BASE}{fn.replace(' ', '%20')}\n")

        print(f"\nUpdated files in {OUTPUT_DIR}/")

        if list(new_unique):
            sorted_new = sorted(new_unique)
            print(f"\nNew first 5: {sorted_new[:5]}")
            print(f"New last 5:  {sorted_new[-5:]}")
    else:
        print("No new files found in pages 1400-3299")

    print(f"{'=' * 70}")

if __name__ == "__main__":
    asyncio.run(main())
