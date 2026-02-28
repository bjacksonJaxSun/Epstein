"""
Bulk download missing DOJ Epstein files using catalog URLs.

Architecture: Headless Playwright browser with worker pool.
Each worker uses a persistent page and page.expect_download + download.save_as()
to capture PDFs (same pattern as download_missing_ds9.py).

Age gate is handled once on a dedicated page; cookies persist across the context.

Reads need_download.txt (output of gap_analysis.py) for the list of files to fetch.

Usage:
    python download_missing_files.py [--dataset N] [--concurrency 4] [--max-files N] [--dry-run]
"""
import argparse
import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).parent
NEED_DOWNLOAD_FILE = SCRIPT_DIR / "need_download.txt"
PROGRESS_FILE = SCRIPT_DIR / "download_progress.txt"
FAILURES_FILE = SCRIPT_DIR / "download_failures.txt"

DEFAULT_FILES_ROOT = Path(r"D:\Personal\Epstein\data\files")

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
DOWNLOAD_TIMEOUT = 60000   # ms
PAGE_TIMEOUT = 30000       # ms
RATE_LIMIT_DELAY = 1.0     # seconds between downloads per worker
MAX_RETRIES = 3

AGE_GATE_KEYWORDS = ('age-verify', 'age_verify', 'age-gate', 'age_gate', '/age/', 'ageverif')

AGE_SELECTORS = [
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


def load_need_download(dataset_filter=None):
    """Load need_download.txt. Returns list of (efta, dataset, url) tuples."""
    if not NEED_DOWNLOAD_FILE.exists():
        print(f"ERROR: {NEED_DOWNLOAD_FILE} not found.")
        print("Run gap_analysis.py first.")
        sys.exit(1)

    entries = []
    with open(NEED_DOWNLOAD_FILE, 'r') as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            parts = line.strip().split('\t')
            if len(parts) >= 3 and parts[0].startswith('EFTA'):
                efta, dataset, url = parts[0], parts[1], parts[2]
                if dataset_filter is not None and dataset != str(dataset_filter):
                    continue
                entries.append((efta, dataset, url))

    return entries


def load_progress():
    """Load set of already-downloaded EFTAs."""
    completed = set()
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and line.startswith('EFTA'):
                    completed.add(line)
    return completed


def append_progress(efta):
    """Mark an EFTA as successfully downloaded."""
    with open(PROGRESS_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{efta}\n")


def append_failure(efta, url, error):
    """Log a failed download."""
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # Sanitize error to ASCII to avoid cp1252 encoding issues on Windows
    error_clean = error.encode('ascii', errors='replace').decode('ascii')
    with open(FAILURES_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{ts}\t{efta}\t{error_clean}\t{url}\n")


def get_output_path(efta, dataset, files_root):
    """Determine the save path using catalog dataset assignment."""
    ds_dir = files_root / f"DataSet_{dataset}"
    ds_dir.mkdir(parents=True, exist_ok=True)
    return ds_dir / f"{efta}.pdf"


def is_age_gate_url(url):
    """Check if a URL indicates age gate redirect."""
    lowered = url.lower()
    return any(kw in lowered for kw in AGE_GATE_KEYWORDS)


async def check_and_handle_age_gate(page, label=""):
    """Check if the current page is an age gate and handle it.

    Called after every page.goto() to ensure the age gate never blocks progress.
    Returns True if an age gate was found and handled, False if no gate detected.
    """
    # Check URL
    if not is_age_gate_url(page.url):
        # Also check page content for inline age gate
        try:
            content = await page.content()
            if 'age-verify' not in content and 'age_verify' not in content:
                return False
        except:
            return False

    if label:
        print(f"  {label} Age gate detected, handling...")

    # Try all selectors
    for selector in AGE_SELECTORS:
        try:
            btn = page.locator(selector)
            if await btn.is_visible(timeout=3000):
                await btn.click()
                if label:
                    print(f"    {label} Auto-clicked: {selector}")
                await page.wait_for_timeout(5000)
                # Verify we left the age gate
                if not is_age_gate_url(page.url):
                    return True
                # Still on gate — try clicking again or try next selector
        except:
            continue

    # Selectors didn't work. Try JavaScript click on common patterns.
    try:
        clicked = await page.evaluate("""() => {
            const btns = document.querySelectorAll('a, button, input[type="submit"]');
            for (const btn of btns) {
                const text = (btn.textContent || btn.value || '').toLowerCase();
                if (text.includes('yes') || text.includes('18') || text.includes('i am')) {
                    btn.click();
                    return true;
                }
            }
            return false;
        }""")
        if clicked:
            if label:
                print(f"    {label} JS-clicked age gate button")
            await page.wait_for_timeout(5000)
            if not is_age_gate_url(page.url):
                return True
    except:
        pass

    # Last resort for non-headless: wait for manual click
    if label:
        print(f"    {label} Auto-click failed. Waiting for manual click (3 min)...")
    try:
        await page.wait_for_url(
            lambda url: not is_age_gate_url(url),
            timeout=180000
        )
        return True
    except PlaywrightTimeout:
        if label:
            print(f"    {label} WARNING: Timeout waiting for age verification.")
        return False


async def goto_with_age_check(page, url, label="", timeout=PAGE_TIMEOUT):
    """Navigate to a URL and automatically handle age gate if it appears.

    Returns the Response object from page.goto().
    """
    response = await page.goto(url, timeout=timeout, wait_until="domcontentloaded")
    await page.wait_for_timeout(1000)

    # Check for age gate and handle it
    if is_age_gate_url(page.url):
        await check_and_handle_age_gate(page, label=label)
        # Re-navigate to the actual target after passing the gate
        response = await page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        await page.wait_for_timeout(1000)

    return response


async def do_age_verification(page, sample_url):
    """Handle initial age verification on a dedicated page."""
    print(f"  Verifying age gate with: {sample_url.split('/')[-1]}")

    for attempt in range(3):
        try:
            await goto_with_age_check(page, sample_url, label="[init]")
            break
        except Exception as e:
            print(f"  Attempt {attempt + 1} failed: {str(e)[:60]}")
            if attempt < 2:
                await page.wait_for_timeout(3000)
            else:
                raise

    if is_age_gate_url(page.url):
        print("  WARNING: Still on age gate after handling.")
        return False

    print("  Age verification OK — file URL accessible.")
    return True


async def worker(worker_id, age_page, api_request, queue, files_root, stats, age_lock, age_state, debug=False):
    """Worker that downloads files using context.request (raw HTTP bytes).

    Uses api_request (shares browser cookies) for actual downloads.
    Falls back to age_page for handling age gates when they appear.
    age_lock + age_state ensure only one worker handles the gate; others just wait and retry.
    """
    label = f"[W{worker_id}]"

    while True:
        try:
            efta, dataset, url = queue.get_nowait()
        except asyncio.QueueEmpty:
            return

        out_path = get_output_path(efta, dataset, files_root)

        # Skip if already on disk
        if out_path.exists() and out_path.stat().st_size > 0:
            stats['skipped'] += 1
            append_progress(efta)
            queue.task_done()
            continue

        await asyncio.sleep(RATE_LIMIT_DELAY)

        for attempt in range(MAX_RETRIES):
            try:
                response = await api_request.get(url, timeout=DOWNLOAD_TIMEOUT)
                status = response.status
                resp_url = response.url
                body = await response.body()

                if debug:
                    ct = response.headers.get('content-type', '')
                    print(f"  {label} {efta}: status={status}, ct={ct}, size={len(body)}")

                # Age gate: check URL and body content
                is_gate = is_age_gate_url(resp_url) or (
                    len(body) < 10000 and (b'age-verify' in body or b'age_verify' in body)
                )

                if is_gate:
                    print(f"  {label} {efta}: Age gate hit, handling...")
                    now = time.time()
                    # If another worker handled the gate recently, just wait and retry
                    if now - age_state['last_handled'] < 30:
                        await asyncio.sleep(3)
                    else:
                        # Try to be the one to handle the gate
                        async with age_lock:
                            # Double-check: maybe another worker handled it while we waited
                            if time.time() - age_state['last_handled'] < 30:
                                await asyncio.sleep(2)
                            else:
                                await goto_with_age_check(age_page, url, label=label)
                                age_state['last_handled'] = time.time()
                        await asyncio.sleep(2)

                    # Retry download
                    response = await api_request.get(url, timeout=DOWNLOAD_TIMEOUT)
                    status = response.status
                    body = await response.body()

                    # Still gated?
                    if is_age_gate_url(response.url) or (
                        len(body) < 10000 and b'age-verify' in body
                    ):
                        stats['age_gate_hits'] += 1
                        append_failure(efta, url, "age_gate_persistent")
                        break

                if status == 404:
                    stats['not_found'] += 1
                    append_failure(efta, url, "http_404")
                    break

                if status != 200:
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(2 ** (attempt + 1))
                        continue
                    stats['failed'] += 1
                    append_failure(efta, url, f"http_{status}")
                    break

                if len(body) < 100:
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(2 ** (attempt + 1))
                        continue
                    stats['failed'] += 1
                    append_failure(efta, url, f"too_small: {len(body)} bytes")
                    break

                if not body[:5].startswith(b'%PDF'):
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(2 ** (attempt + 1))
                        continue
                    stats['failed'] += 1
                    append_failure(efta, url, f"not_pdf: {body[:20]}")
                    break

                # Write file
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with open(out_path, 'wb') as f:
                    f.write(body)

                stats['downloaded'] += 1
                append_progress(efta)
                break

            except PlaywrightTimeout:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** (attempt + 1))
                    continue
                stats['failed'] += 1
                append_failure(efta, url, "timeout")
                break
            except Exception as e:
                if debug:
                    print(f"  {label} {efta}: exception: {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** (attempt + 1))
                    continue
                stats['failed'] += 1
                append_failure(efta, url, str(e)[:80])
                break

        queue.task_done()

        # Abort if too many age gate hits
        if stats['age_gate_hits'] >= 20:
            print(f"  {label} Too many age gate failures, stopping.")
            while not queue.empty():
                try:
                    queue.get_nowait()
                    queue.task_done()
                except asyncio.QueueEmpty:
                    break
            return


async def run_downloads(entries, files_root, concurrency, dry_run, headless=True, debug=False):
    """Run concurrent downloads using Playwright worker pool."""
    stats = {
        'downloaded': 0,
        'skipped': 0,
        'failed': 0,
        'not_found': 0,
        'age_gate_hits': 0,
    }

    if dry_run:
        print(f"\n[DRY RUN] Would download {len(entries)} files:")
        by_ds = {}
        for efta, ds, url in entries:
            by_ds[ds] = by_ds.get(ds, 0) + 1
        for ds in sorted(by_ds.keys(), key=lambda x: int(x) if x.isdigit() else 999):
            print(f"  Dataset {ds}: {by_ds[ds]} files")
        return stats

    print(f"\n[Browser setup] Launching Chromium ({'headless' if headless else 'visible'})...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            user_agent=USER_AGENT,
            accept_downloads=True,
        )

        # Dedicated age gate page (stays open, holds cookies)
        age_page = await context.new_page()
        sample_url = entries[0][2]
        verified = await do_age_verification(age_page, sample_url)
        if not verified:
            print("  Age verification failed. Aborting.")
            await browser.close()
            return stats

        # Work queue
        queue = asyncio.Queue()
        for entry in entries:
            queue.put_nowait(entry)

        # API request context shares cookies with browser
        api_request = context.request

        # Lock so only one worker handles age gate at a time
        age_lock = asyncio.Lock()
        age_state = {'last_handled': 0.0}

        print(f"\nStarting downloads: {len(entries)} files, {concurrency} workers")
        print(f"Output root: {files_root}")
        start_time = time.time()

        # Workers share the age_page for gate handling, use api_request for downloads
        worker_tasks = []
        for i in range(concurrency):
            task = asyncio.create_task(
                worker(i, age_page, api_request, queue, files_root, stats, age_lock, age_state, debug=debug)
            )
            worker_tasks.append(task)

        # Progress reporter
        total = len(entries)
        while not all(t.done() for t in worker_tasks):
            await asyncio.sleep(5)
            done_count = total - queue.qsize()
            elapsed = time.time() - start_time
            rate = done_count / elapsed if elapsed > 0 else 0
            print(
                f"  Progress: {done_count}/{total} "
                f"({stats['downloaded']} ok, {stats['skipped']} skip, "
                f"{stats['failed']} fail, {stats['not_found']} 404, "
                f"{stats['age_gate_hits']} gate) "
                f"[{rate:.1f}/s]"
            )

        await asyncio.gather(*worker_tasks)

        elapsed = time.time() - start_time
        print(f"\nDownloads completed in {elapsed:.1f}s")

        await age_page.close()
        await browser.close()

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Download missing DOJ Epstein files from catalog URLs"
    )
    parser.add_argument('--dataset', type=int, default=None,
                        help='Only download files from this dataset number')
    parser.add_argument('--concurrency', type=int, default=4,
                        help='Number of simultaneous browser tabs (default: 4)')
    parser.add_argument('--max-files', type=int, default=None,
                        help='Maximum number of files to download')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be downloaded without actually downloading')
    parser.add_argument('--files-root', type=str, default=str(DEFAULT_FILES_ROOT),
                        help=f'Root directory for saving files (default: {DEFAULT_FILES_ROOT})')
    parser.add_argument('--visible', action='store_true',
                        help='Show browser window (default: headless)')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug output')
    args = parser.parse_args()

    files_root = Path(args.files_root)

    print(f"{'='*70}")
    print(f"DOJ EPSTEIN FILES — BULK DOWNLOADER")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")

    # Load entries
    print(f"\nLoading download list from {NEED_DOWNLOAD_FILE}...")
    entries = load_need_download(dataset_filter=args.dataset)
    print(f"  Total entries: {len(entries)}")

    # Filter out already-completed
    completed = load_progress()
    entries = [(e, d, u) for e, d, u in entries if e not in completed]
    print(f"  Already completed: {len(completed)}")
    print(f"  Remaining: {len(entries)}")

    if not entries:
        print("\nAll files already downloaded!")
        return

    if args.max_files:
        entries = entries[:args.max_files]
        print(f"  Limited to: {len(entries)} files (--max-files {args.max_files})")

    by_ds = {}
    for efta, ds, url in entries:
        by_ds[ds] = by_ds.get(ds, 0) + 1
    print(f"\n  By dataset:")
    for ds in sorted(by_ds.keys(), key=lambda x: int(x) if x.isdigit() else 999):
        print(f"    Dataset {ds}: {by_ds[ds]} files")

    stats = asyncio.run(run_downloads(
        entries, files_root, args.concurrency, args.dry_run,
        headless=not args.visible, debug=args.debug
    ))

    print(f"\n{'='*70}")
    print(f"DOWNLOAD SUMMARY")
    print(f"{'='*70}")
    print(f"  Downloaded:    {stats['downloaded']:>8}")
    print(f"  Skipped:       {stats['skipped']:>8}  (already on disk)")
    print(f"  Failed:        {stats['failed']:>8}")
    print(f"  Not found:     {stats['not_found']:>8}  (HTTP 404)")
    print(f"  Age gate hits: {stats['age_gate_hits']:>8}")
    total_processed = stats['downloaded'] + stats['skipped'] + stats['failed'] + stats['not_found']
    print(f"  Total:         {total_processed:>8}")
    print(f"{'='*70}")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if stats['failed'] > 0:
        print(f"\nFailed downloads logged to: {FAILURES_FILE}")
    if stats['age_gate_hits'] > 0:
        print(f"\nWARNING: {stats['age_gate_hits']} age gate redirects detected.")
        print("Re-run the script to get a fresh browser session.")


if __name__ == "__main__":
    main()
