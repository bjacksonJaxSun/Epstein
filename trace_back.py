import asyncio
from playwright.async_api import async_playwright

async def trace_back():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        await page.goto('https://www.justice.gov/epstein/doj-disclosures/data-set-9-files')
        await page.wait_for_timeout(3000)

        try:
            robot = page.locator('input[value="I am not a robot"]')
            if await robot.is_visible(timeout=2000):
                await robot.click()
                await page.wait_for_timeout(3000)
        except:
            pass

        try:
            age = page.locator('#age-button-yes')
            if await age.is_visible(timeout=2000):
                await age.click()
                await page.wait_for_timeout(3000)
        except:
            pass

        # Check pages going backwards from 9996
        for test_page in range(9996, 9970, -1):
            url = f'https://www.justice.gov/epstein/doj-disclosures/data-set-9-files?page={test_page}'
            await page.goto(url, timeout=15000)
            await page.wait_for_timeout(1000)

            links = await page.locator('a[href*="DataSet%209"][href*=".pdf"]').all()
            if links:
                first_href = await links[0].get_attribute('href')
                last_href = await links[-1].get_attribute('href')
                first_file = first_href.split('/')[-1] if first_href else '?'
                last_file = last_href.split('/')[-1] if last_href else '?'
                print(f'Page {test_page}: {len(links):2d} files | {first_file} to {last_file}')

                is_last_block = (last_file == 'EFTA01262781.pdf' or first_file == 'EFTA01262778.pdf')
                is_first_block = (first_file == 'EFTA00039025.pdf')

                if not is_last_block and not is_first_block:
                    print(f'\nPage {test_page}: Last page with UNIQUE progressing files!')
                    print(f'Total unique pages: 0 through {test_page}')
                    break

        await browser.close()

asyncio.run(trace_back())
