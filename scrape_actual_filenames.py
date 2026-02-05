"""
Scrape actual filenames from Justice.gov Dataset 9 page
This will get the REAL file list instead of using the incorrect Archive.org list
"""
import asyncio
import json
import re
from playwright.async_api import async_playwright

async def scrape_dataset9_files():
    """Scrape all actual filenames from Dataset 9 pages"""
    all_files = []

    async with async_playwright() as p:
        print("Opening browser...")
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # Navigate to Dataset 9 page
        print("Navigating to Dataset 9 page...")
        await page.goto("https://www.justice.gov/epstein/doj-disclosures/data-set-9-files")

        # Wait for page to load
        await page.wait_for_timeout(3000)

        # Handle age verification
        print("\nLooking for age verification buttons...")

        # Try to find and click "I am not a robot" button
        try:
            robot_button = page.locator('input[value="I am not a robot"]')
            if await robot_button.is_visible(timeout=2000):
                print("Clicking 'I am not a robot' button...")
                await robot_button.click()
                await page.wait_for_timeout(3000)
        except:
            print("No robot button found or already verified")

        # Try to find and click age verification button
        try:
            age_button = page.locator('#age-button-yes, input[value*="18"], button:has-text("Yes")')
            if await age_button.is_visible(timeout=2000):
                print("Clicking age verification button...")
                await age_button.click()
                await page.wait_for_timeout(3000)
        except:
            print("No age button found or already verified")

        # Now scrape files from all pages
        # Start with page 0 and manually increment through pages
        max_pages = 100  # Safety limit

        for page_num in range(max_pages):
            print(f"\n{'='*80}")
            print(f"Scraping Dataset 9 - Page {page_num}...")
            print(f"{'='*80}")

            # Navigate to specific page of Dataset 9
            url = f"https://www.justice.gov/epstein/doj-disclosures/data-set-9-files?page={page_num}"
            print(f"URL: {url}")

            try:
                await page.goto(url, timeout=30000)
                await page.wait_for_timeout(3000)
            except Exception as e:
                print(f"Error loading page {page_num}: {e}")
                break

            # Find all PDF links on current page
            pdf_links = await page.locator('a[href*="DataSet%209"][href*=".pdf"], a[href*="DataSet 9"][href*=".pdf"]').all()

            page_files = []
            for link in pdf_links:
                href = await link.get_attribute('href')
                if href and href.endswith('.pdf'):
                    # Extract filename from URL
                    filename = href.split('/')[-1].replace('%20', ' ')
                    # Make sure it's from Dataset 9
                    if 'EFTA' in filename:
                        page_files.append(filename)

            print(f"Found {len(page_files)} files on page {page_num}")

            if len(page_files) == 0:
                print("No files found - reached end of dataset")
                break

            if page_files:
                print(f"  First: {page_files[0]}")
                print(f"  Last: {page_files[-1]}")

            all_files.extend(page_files)

            # Continue to next page (we'll stop when we get no files)

        await browser.close()

    return all_files

async def main():
    print("="*80)
    print("Dataset 9 - Real Filename Scraper")
    print("="*80)
    print("\nThis will scrape the ACTUAL filenames from Justice.gov")
    print("instead of using the incorrect Archive.org generated list.\n")

    files = await scrape_dataset9_files()

    print("\n" + "="*80)
    print("SCRAPING COMPLETE")
    print("="*80)
    print(f"\nTotal files found: {len(files)}")
    print(f"Unique files: {len(set(files))}")

    # Remove duplicates and sort
    unique_files = sorted(set(files))

    # Save to JSON
    output_file = "epstein_files/DataSet_9/actual_filenames.json"
    with open(output_file, 'w') as f:
        json.dump(unique_files, f, indent=2)

    print(f"\nSaved to: {output_file}")

    # Save as simple list
    output_txt = "epstein_files/DataSet_9/actual_filenames.txt"
    with open(output_txt, 'w') as f:
        for filename in unique_files:
            f.write(f"{filename}\n")

    print(f"Saved to: {output_txt}")

    # Show sample
    print("\nFirst 10 files:")
    for i, filename in enumerate(unique_files[:10], 1):
        print(f"  {i}. {filename}")

    print("\nLast 10 files:")
    for i, filename in enumerate(unique_files[-10:], len(unique_files)-9):
        print(f"  {i}. {filename}")

    # Create URL list
    base_url = "https://www.justice.gov/epstein/files/DataSet%209/"
    output_urls = "epstein_files/DataSet_9/actual_download_urls.txt"
    with open(output_urls, 'w') as f:
        for filename in unique_files:
            url = base_url + filename.replace(' ', '%20')
            f.write(f"{url}\n")

    print(f"\nDownload URLs saved to: {output_urls}")

    print("\n" + "="*80)
    print(f"SUCCESS: Found {len(unique_files)} actual files")
    print(f"This is MUCH smaller than the 1.2M in the Archive.org list!")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())
