"""
Scrape filenames from Justice.gov Dataset 10.
Step 1: Binary search to find last page
Step 2: Scrape all pages
"""
import asyncio
import json
import os
from playwright.async_api import async_playwright

OUTPUT_DIR = "epstein_files/DataSet_10"
BASE_URL = "https://www.justice.gov/epstein/doj-disclosures/data-set-10-files"
DOWNLOAD_BASE = "https://www.justice.gov/epstein/files/DataSet%2010/"

async def check_page_has_files(page, page_num):
    """Check if a page has PDF files"""
    url = f"{BASE_URL}?page={page_num}"
    try:
        await page.goto(url, timeout=15000, wait_until="domcontentloaded")
        await page.wait_for_timeout(1000)
        count = await page.locator('a[href*="DataSet%2010"][href*=".pdf"], a[href*="DataSet 10"][href*=".pdf"]').count()
        return count
    except:
        return 0

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

async def find_last_page(page):
    """Binary search for last page"""
    print("\n[STEP 1] Finding last page (binary search)...\n")

    # Start high
    low, high = 0, 50000

    # First check if page 0 has files
    count = await check_page_has_files(page, 0)
    if count == 0:
        print("Page 0 has no files!")
        return -1
    print(f"  Page 0: {count} files")

    # Find upper bound with exponential search
    test = 100
    while test <= 50000:
        print(f"  Testing page {test}...", end=" ")
        count = await check_page_has_files(page, test)
        if count > 0:
            # Check if it's wrapping (showing page 0 files)
            files = await get_page_files(page, test)
            files_p0 = await get_page_files(page, 0)
            if files and files_p0 and files[0] == files_p0[0]:
                print(f"WRAPPING (shows page 0 files)")
                high = test
                break
            else:
                print(f"{count} files (unique)")
                low = test
                test = test * 2
        else:
            print(f"EMPTY")
            high = test
            break

    # Binary search
    print(f"\n  Binary search between {low} and {high}...")
    while low < high - 1:
        mid = (low + high) // 2
        print(f"  Testing page {mid}...", end=" ")

        count = await check_page_has_files(page, mid)
        if count > 0:
            # Check for wrapping
            files = await get_page_files(page, mid)
            files_p0 = await get_page_files(page, 0)
            if files and files_p0 and files[0] == files_p0[0]:
                print(f"WRAPPING")
                high = mid
            else:
                print(f"{count} unique files")
                low = mid
        else:
            print(f"EMPTY")
            high = mid

    print(f"\n  Last page with unique content: {low}")
    return low

async def scrape_all(page, last_page):
    """Scrape all pages"""
    print(f"\n[STEP 2] Scraping pages 0 through {last_page}...\n")

    all_files = []
    consecutive_empty = 0

    for page_num in range(last_page + 1):
        files = await get_page_files(page, page_num)

        if len(files) == 0:
            consecutive_empty += 1
            if consecutive_empty >= 20:
                print(f"  [{page_num}] 20 consecutive empty pages - stopping")
                break
        else:
            consecutive_empty = 0
            all_files.extend(files)

        if page_num % 10 == 0:
            pct = (page_num / (last_page + 1)) * 100
            print(f"  [{page_num}/{last_page}] {pct:.1f}% - {len(all_files)} files")

    return all_files

async def main():
    print("=" * 70)
    print("Dataset 10 - Filename Scraper")
    print("=" * 70)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # Age verification
        await do_age_verification(page)

        # Find last page
        last_page = await find_last_page(page)

        if last_page < 0:
            print("ERROR: Could not find any files")
            await browser.close()
            return

        print(f"\nTotal pages: {last_page + 1}")

        # Scrape all pages
        all_files = await scrape_all(page, last_page)

        await browser.close()

    # Deduplicate and sort
    unique_files = sorted(set(all_files))

    print(f"\n{'=' * 70}")
    print(f"SCRAPING COMPLETE")
    print(f"{'=' * 70}")
    print(f"Total collected: {len(all_files)}")
    print(f"Unique files: {len(unique_files)}")

    # Save files
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with open(os.path.join(OUTPUT_DIR, "actual_filenames.json"), 'w') as f:
        json.dump(unique_files, f, indent=2)

    with open(os.path.join(OUTPUT_DIR, "actual_filenames.txt"), 'w') as f:
        for fn in unique_files:
            f.write(f"{fn}\n")

    with open(os.path.join(OUTPUT_DIR, "actual_download_urls.txt"), 'w') as f:
        for fn in unique_files:
            f.write(f"{DOWNLOAD_BASE}{fn.replace(' ', '%20')}\n")

    print(f"\nSaved {len(unique_files)} unique files to {OUTPUT_DIR}/")
    print(f"  actual_filenames.txt")
    print(f"  actual_download_urls.txt")

    if unique_files:
        print(f"\nFirst 5: {unique_files[:5]}")
        print(f"Last 5:  {unique_files[-5:]}")

    print(f"{'=' * 70}")

if __name__ == "__main__":
    asyncio.run(main())
