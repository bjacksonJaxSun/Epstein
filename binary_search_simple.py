"""
Simple binary search - start high, split in half based on results
"""
import asyncio
from playwright.async_api import async_playwright

async def check_page(page, page_num):
    """Check if page has files, return count"""
    url = f"https://www.justice.gov/epstein/doj-disclosures/data-set-9-files?page={page_num}"
    try:
        await page.goto(url, timeout=15000, wait_until="domcontentloaded")
        await page.wait_for_timeout(1000)
        count = await page.locator('a[href*="DataSet%209"][href*=".pdf"]').count()
        return count
    except:
        return 0

async def find_last_page():
    async with async_playwright() as p:
        print("Binary Search - Starting Very High\n")

        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # Age verification
        print("Age verification...")
        await page.goto("https://www.justice.gov/epstein/doj-disclosures/data-set-9-files")
        await page.wait_for_timeout(3000)

        try:
            robot = page.locator('input[value="I am not a robot"]')
            if await robot.is_visible(timeout=2000):
                await robot.click()
                await page.wait_for_timeout(3000)
        except: pass

        try:
            age = page.locator('#age-button-yes')
            if await age.is_visible(timeout=2000):
                await age.click()
                await page.wait_for_timeout(3000)
        except: pass

        print("Starting binary search...\n")

        # Start at 12000 based on sampling
        low = 9000
        high = 12000

        iteration = 0
        while low < high - 1:
            iteration += 1
            mid = (low + high) // 2

            print(f"[{iteration}] Range: {low} - {high}")
            print(f"     Testing page {mid}...", end=" ")

            count = await check_page(page, mid)

            if count > 0:
                print(f"FOUND {count} files")
                print(f"     -> Last page is {mid} or higher")
                print(f"     -> Searching UPPER half ({mid} - {high})\n")
                low = mid  # Search upper half
            else:
                print(f"EMPTY")
                print(f"     -> Last page is below {mid}")
                print(f"     -> Searching LOWER half ({low} - {mid})\n")
                high = mid  # Search lower half

        # Final verification
        print(f"Final check: page {low}...", end=" ")
        count_low = await check_page(page, low)
        print(f"{count_low} files")

        print(f"Final check: page {low + 1}...", end=" ")
        count_next = await check_page(page, low + 1)
        print(f"{count_next} files")

        await browser.close()

        print("\n" + "=" * 60)
        print(f"RESULT: Last page is {low}")
        print(f"Total pages: {low + 1} (pages 0 through {low})")
        print("=" * 60)

        return low

if __name__ == "__main__":
    asyncio.run(find_last_page())
