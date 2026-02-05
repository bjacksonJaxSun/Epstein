"""
Binary search to find the last page quickly
"""
import asyncio
from playwright.async_api import async_playwright

async def has_files(page, page_num):
    """Check if a page has files"""
    url = f"https://www.justice.gov/epstein/doj-disclosures/data-set-9-files?page={page_num}"
    try:
        await page.goto(url, timeout=15000)
        await page.wait_for_timeout(1500)
        pdf_count = await page.locator('a[href*="DataSet%209"][href*=".pdf"]').count()
        return pdf_count > 0
    except:
        return False

async def find_last_page():
    """Use binary search to find last page"""

    async with async_playwright() as p:
        print("Opening browser...")
        browser = await p.chromium.launch(headless=False)
        page_obj = await browser.new_page()

        # Handle age verification
        print("Handling age verification...")
        await page_obj.goto("https://www.justice.gov/epstein/doj-disclosures/data-set-9-files")
        await page_obj.wait_for_timeout(3000)

        try:
            robot_button = page_obj.locator('input[value="I am not a robot"]')
            if await robot_button.is_visible(timeout=2000):
                await robot_button.click()
                await page_obj.wait_for_timeout(3000)
        except:
            pass

        try:
            age_button = page_obj.locator('#age-button-yes')
            if await age_button.is_visible(timeout=2000):
                await age_button.click()
                await page_obj.wait_for_timeout(3000)
        except:
            pass

        # Binary search for last page
        print("\nSearching for last page...")
        low, high = 0, 3000  # Start with reasonable upper bound

        # First, find an upper bound that has no files
        print("Finding upper bound...")
        test = 200
        while test <= 3000:
            print(f"  Testing page {test}...")
            if await has_files(page_obj, test):
                print(f"    Page {test} has files, trying higher...")
                low = test
                test = test * 2 if test < 500 else test + 100
            else:
                print(f"    Page {test} is empty - found upper bound")
                high = test
                break

        # Binary search between low and high
        print(f"\nBinary search between {low} and {high}...")
        while low < high - 1:
            mid = (low + high) // 2
            print(f"  Testing page {mid}...")
            if await has_files(page_obj, mid):
                print(f"    Page {mid} has files")
                low = mid
            else:
                print(f"    Page {mid} is empty")
                high = mid

        # Verify the last page
        print(f"\nVerifying last page is {low}...")
        has_current = await has_files(page_obj, low)
        has_next = await has_files(page_obj, low + 1)

        if has_current and not has_next:
            print(f"\nCONFIRMED: Last page is {low}")
            print(f"Total pages: {low + 1} (pages 0-{low})")
        else:
            print(f"\nWARNING: Need manual check around page {low}")

        await browser.close()
        return low

if __name__ == "__main__":
    last_page = asyncio.run(find_last_page())
    print(f"\n{'='*60}")
    print(f"RESULT: Scrape pages 0 through {last_page}")
    print(f"{'='*60}")
