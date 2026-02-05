import { chromium } from 'playwright';

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });

// Capture console messages
const consoleMessages = [];
page.on('console', msg => consoleMessages.push(`[${msg.type()}] ${msg.text()}`));
page.on('pageerror', err => consoleMessages.push(`[PAGE ERROR] ${err.message}`));

await page.goto('http://localhost:5173', { waitUntil: 'networkidle', timeout: 15000 });
await page.waitForTimeout(5000);

// Screenshot
await page.screenshot({ path: 'dashboard-screenshot.png', fullPage: false });

// Console output
console.log('=== CONSOLE MESSAGES ===');
consoleMessages.forEach(m => console.log(m));

// Check if root div has content
const rootHTML = await page.evaluate(() => {
  const root = document.getElementById('root');
  return root ? root.innerHTML.substring(0, 2000) : 'ROOT NOT FOUND';
});
console.log('\n=== ROOT HTML (first 2000 chars) ===');
console.log(rootHTML);

// Get full page text
const bodyText = await page.evaluate(() => document.body.innerText);
console.log('\n=== BODY TEXT ===');
console.log(bodyText || '(empty)');

await browser.close();
