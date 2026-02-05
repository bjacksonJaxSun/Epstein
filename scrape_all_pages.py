"""
Scrape ALL filenames from Justice.gov Dataset 9 (pages 0 through 9995)
Saves progress every 100 pages so it can resume if interrupted.
"""
import asyncio
import json
import os
from playwright.async_api import async_playwright

PROGRESS_FILE = "epstein_files/DataSet_9/scrape_progress.json"
OUTPUT_DIR = "epstein_files/DataSet_9"
MAX_PAGE = 9996  # Pages 0-9995 have unique content

def load_progress():
    """Load saved progress"""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {"last_page": -1, "files": []}

def save_progress(last_page, files):
    """Save progress to disk"""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump({"last_page": last_page, "files": files}, f)

async def scrape_all():
    progress = load_progress()
    start_page = progress["last_page"] + 1
    all_files = progress["files"]

    print("=" * 70)
    print(f"Dataset 9 - Full Scraper (pages 0 through {MAX_PAGE - 1})")
    print("=" * 70)

    if start_page > 0:
        print(f"\nResuming from page {start_page} ({len(all_files)} files collected)")
    else:
        print(f"\nStarting fresh scrape of {MAX_PAGE} pages")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # Age verification
        print("\nAge verification...")
        await page.goto("https://www.justice.gov/epstein/doj-disclosures/data-set-9-files")
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

        print(f"\nScraping pages {start_page} through {MAX_PAGE - 1}...\n")

        consecutive_empty = 0

        for page_num in range(start_page, MAX_PAGE):
            url = f"https://www.justice.gov/epstein/doj-disclosures/data-set-9-files?page={page_num}"

            try:
                await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                await page.wait_for_timeout(1000)
            except Exception as e:
                print(f"[{page_num}] Error loading: {e}")
                continue

            # Find PDF links
            links = await page.locator('a[href*="DataSet%209"][href*=".pdf"]').all()

            page_files = []
            for link in links:
                href = await link.get_attribute('href')
                if href and href.endswith('.pdf'):
                    filename = href.split('/')[-1].replace('%20', ' ')
                    if 'EFTA' in filename:
                        page_files.append(filename)

            if len(page_files) == 0:
                consecutive_empty += 1
                if consecutive_empty >= 20:
                    print(f"[{page_num}] 20 consecutive empty pages - stopping")
                    break
                if consecutive_empty % 5 == 0:
                    print(f"[{page_num}] {consecutive_empty} consecutive empty pages (continuing...)")
            else:
                consecutive_empty = 0

            all_files.extend(page_files)

            # Progress display
            if page_num % 10 == 0:
                pct = (page_num / MAX_PAGE) * 100
                print(f"[{page_num}/{MAX_PAGE}] {pct:.1f}% - {len(all_files)} files collected")

            # Save progress every 100 pages
            if page_num % 100 == 0 and page_num > 0:
                save_progress(page_num, all_files)
                print(f"  [SAVED] Progress saved at page {page_num}")

        await browser.close()

    # Final save
    save_progress(MAX_PAGE - 1, all_files)

    # Deduplicate and sort
    unique_files = sorted(set(all_files))

    print(f"\n{'=' * 70}")
    print(f"SCRAPING COMPLETE")
    print(f"{'=' * 70}")
    print(f"Total collected: {len(all_files)}")
    print(f"Unique files: {len(unique_files)}")

    # Save final lists
    with open(os.path.join(OUTPUT_DIR, "actual_filenames.json"), 'w') as f:
        json.dump(unique_files, f, indent=2)

    with open(os.path.join(OUTPUT_DIR, "actual_filenames.txt"), 'w') as f:
        for fn in unique_files:
            f.write(f"{fn}\n")

    base_url = "https://www.justice.gov/epstein/files/DataSet%209/"
    with open(os.path.join(OUTPUT_DIR, "actual_download_urls.txt"), 'w') as f:
        for fn in unique_files:
            f.write(f"{base_url}{fn.replace(' ', '%20')}\n")

    print(f"\nSaved {len(unique_files)} unique files to:")
    print(f"  actual_filenames.txt")
    print(f"  actual_filenames.json")
    print(f"  actual_download_urls.txt")

    print(f"\nFirst 5: {unique_files[:5]}")
    print(f"Last 5:  {unique_files[-5:]}")
    print(f"{'=' * 70}")

if __name__ == "__main__":
    asyncio.run(scrape_all())
