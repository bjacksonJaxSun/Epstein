"""
Verify we got all pages by checking beyond page 99
"""
import asyncio
from playwright.async_api import async_playwright

async def check_final_pages():
    """Check pages 99-110 to ensure we didn't miss any"""

    async with async_playwright() as p:
        print("Opening browser...")
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # Navigate and handle age verification first
        print("Handling age verification...")
        await page.goto("https://www.justice.gov/epstein/doj-disclosures/data-set-9-files")
        await page.wait_for_timeout(3000)

        # Click verification buttons
        try:
            robot_button = page.locator('input[value="I am not a robot"]')
            if await robot_button.is_visible(timeout=2000):
                await robot_button.click()
                await page.wait_for_timeout(3000)
        except:
            pass

        try:
            age_button = page.locator('#age-button-yes')
            if await age_button.is_visible(timeout=2000):
                await age_button.click()
                await page.wait_for_timeout(3000)
        except:
            pass

        # Now check pages starting from 99
        for page_num in range(99, 111):  # Check 99-110
            print(f"\nChecking page {page_num}...")
            url = f"https://www.justice.gov/epstein/doj-disclosures/data-set-9-files?page={page_num}"

            try:
                await page.goto(url, timeout=30000)
                await page.wait_for_timeout(2000)

                # Count PDF links
                pdf_links = await page.locator('a[href*="DataSet%209"][href*=".pdf"], a[href*="DataSet 9"][href*=".pdf"]').count()

                print(f"  Page {page_num}: {pdf_links} files")

                if pdf_links == 0:
                    print(f"\n✓ Page {page_num} is empty - we got all pages!")
                    print(f"✓ Total pages: {page_num} (pages 0-{page_num-1})")
                    break

            except Exception as e:
                print(f"  Error on page {page_num}: {e}")
                break

        await browser.close()

if __name__ == "__main__":
    asyncio.run(check_final_pages())
