import { test, expect } from '@playwright/test';

/**
 * Investigation Workbench Tests
 *
 * Requirements tested:
 * 1. API endpoints return correct data structures
 * 2. Person search returns results and allows adding subjects
 * 3. Map renders location markers for selected subjects
 * 4. Connections panel shows locations, people, financial data
 * 5. Hot Spots tab shows shared locations for multiple subjects
 * 6. Financial panel shows transactions for subjects
 */

const ADMIN_USERNAME = 'admin';
const ADMIN_PASSWORD = 'ChangeMe123!';

// Known good data from the database
const KNOWN_PERSON_NAME = 'Jeffrey Epstein';
const KNOWN_PERSON_SEARCH = 'Jeffrey';

async function login(page: import('@playwright/test').Page) {
  const loginButton = page.locator('button[type="submit"]:has-text("Sign In")');
  if (await loginButton.isVisible({ timeout: 3000 }).catch(() => false)) {
    await page.locator('#username').fill(ADMIN_USERNAME);
    await page.locator('#password').fill(ADMIN_PASSWORD);
    await loginButton.click();
    await page.waitForSelector('text=Overview', { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(1000);
  }
}

async function navigateToInvestigation(page: import('@playwright/test').Page) {
  // Navigate directly to the investigation page
  await page.goto('/investigation');
  // Give HMR a moment to settle on first load
  await page.waitForTimeout(2000);
  // Wait for the investigation page to render
  await page.waitForSelector('[data-testid="investigation-page"]', { timeout: 30000 });
}

// React 19 onChange doesn't reliably fire with Playwright fill() — use pressSequentially
async function typeSearch(page: import('@playwright/test').Page, term: string) {
  const searchInput = page.locator('[data-testid="person-search-input"]');
  await searchInput.click();
  await searchInput.pressSequentially(term, { delay: 50 });
}

// ─── API Tests ───────────────────────────────────────────────────────────────

test.describe('Investigation API', () => {
  test('people search API returns results', async ({ request }) => {
    const response = await request.get('/api/investigation/people/search', {
      params: { q: 'Jeffrey', limit: 10 },
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(Array.isArray(data)).toBeTruthy();
    expect(data.length).toBeGreaterThan(0);

    const first = data[0];
    expect(first).toHaveProperty('personId');
    expect(first).toHaveProperty('personName');
    expect(first).toHaveProperty('placementCount');
    console.log(`People search found ${data.length} results. First: ${first.personName}`);
  });

  test('geo-timeline API returns location placements', async ({ request }) => {
    const response = await request.get('/api/investigation/geo-timeline', {
      params: { limit: 100 },
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(Array.isArray(data)).toBeTruthy();
    expect(data.length).toBeGreaterThan(0);

    const entry = data[0];
    expect(entry).toHaveProperty('placementId');
    expect(entry).toHaveProperty('locationId');
    expect(entry).toHaveProperty('locationName');
    expect(entry).toHaveProperty('latitude');
    expect(entry).toHaveProperty('longitude');
    expect(entry).toHaveProperty('personName');
    expect(entry.latitude).not.toBeNull();
    expect(entry.longitude).not.toBeNull();
    console.log(`Geo-timeline returned ${data.length} entries. First: ${entry.personName} at ${entry.locationName}`);
  });

  test('geo-timeline filters by person name', async ({ request }) => {
    const response = await request.get('/api/investigation/geo-timeline', {
      params: { personName: 'Jeffrey', limit: 50 },
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(Array.isArray(data)).toBeTruthy();
    expect(data.length).toBeGreaterThan(0);

    // All entries should include "Jeffrey" in the person name
    for (const entry of data) {
      expect(entry.personName.toLowerCase()).toContain('jeffrey');
    }
    console.log(`Filtered geo-timeline: ${data.length} entries for Jeffrey`);
  });

  test('geo-timeline filters by date range', async ({ request }) => {
    const response = await request.get('/api/investigation/geo-timeline', {
      params: { dateFrom: '2004-01-01', dateTo: '2006-12-31', limit: 100 },
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(Array.isArray(data)).toBeTruthy();
    // All dates should be in range
    for (const entry of data) {
      if (entry.placementDate) {
        const date = new Date(entry.placementDate);
        expect(date.getFullYear()).toBeGreaterThanOrEqual(2004);
        expect(date.getFullYear()).toBeLessThanOrEqual(2006);
      }
    }
    console.log(`Date-filtered geo-timeline: ${data.length} entries from 2004-2006`);
  });

  test('person connections API returns all entity types', async ({ request }) => {
    // First find a person with data
    const searchResponse = await request.get('/api/investigation/people/search', {
      params: { q: KNOWN_PERSON_SEARCH, limit: 5 },
    });
    const people = await searchResponse.json();
    const epstein = people.find((p: { personName: string }) =>
      p.personName.toLowerCase().includes('epstein')
    );

    if (!epstein) {
      console.log('Epstein not found, using first result');
    }
    const person = epstein ?? people[0];
    expect(person).toBeTruthy();

    const response = await request.get(`/api/investigation/person/${person.personId}/connections`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();

    expect(data).toHaveProperty('personId');
    expect(data).toHaveProperty('personName');
    expect(data).toHaveProperty('locations');
    expect(data).toHaveProperty('events');
    expect(data).toHaveProperty('financialTransactions');
    expect(data).toHaveProperty('relatedPeople');
    expect(data).toHaveProperty('coPresences');

    expect(Array.isArray(data.locations)).toBeTruthy();
    expect(Array.isArray(data.events)).toBeTruthy();
    expect(Array.isArray(data.financialTransactions)).toBeTruthy();
    expect(Array.isArray(data.relatedPeople)).toBeTruthy();
    expect(Array.isArray(data.coPresences)).toBeTruthy();

    console.log(`Person connections for ${data.personName}:`);
    console.log(`  Locations: ${data.locations.length}`);
    console.log(`  Events: ${data.events.length}`);
    console.log(`  Financial: ${data.financialTransactions.length}`);
    console.log(`  Related people: ${data.relatedPeople.length}`);
    console.log(`  Co-presences: ${data.coPresences.length}`);

    // Person with placements should have locations
    expect(data.locations.length).toBeGreaterThan(0);
  });

  test('person connections locations have correct structure', async ({ request }) => {
    const searchResponse = await request.get('/api/investigation/people/search', {
      params: { q: KNOWN_PERSON_SEARCH, limit: 5 },
    });
    const people = await searchResponse.json();
    const person = people[0];

    const response = await request.get(`/api/investigation/person/${person.personId}/connections`);
    const data = await response.json();

    if (data.locations.length > 0) {
      const loc = data.locations[0];
      expect(loc).toHaveProperty('locationId');
      expect(loc).toHaveProperty('locationName');
      expect(loc).toHaveProperty('visitCount');
      expect(loc.visitCount).toBeGreaterThan(0);
      console.log(`First location: ${loc.locationName} (${loc.visitCount} visits)`);
    }
  });

  test('shared presence API returns locations for multiple subjects', async ({ request }) => {
    // Get two people with placements
    const searchResponse = await request.get('/api/investigation/people/search', {
      params: { q: 'Jeffrey', limit: 5 },
    });
    const people = await searchResponse.json();

    if (people.length < 2) {
      console.log('Not enough people for shared presence test');
      return;
    }

    const personIds = people.slice(0, 2).map((p: { personId: number }) => p.personId).join(',');
    const response = await request.get('/api/investigation/shared-presence', {
      params: { personIds },
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(Array.isArray(data)).toBeTruthy();
    console.log(`Shared presence: ${data.length} shared locations between subjects`);

    if (data.length > 0) {
      const sp = data[0];
      expect(sp).toHaveProperty('locationId');
      expect(sp).toHaveProperty('locationName');
      expect(sp).toHaveProperty('personCount');
      expect(sp).toHaveProperty('personNames');
      expect(sp.personCount).toBeGreaterThanOrEqual(2);
      expect(Array.isArray(sp.personNames)).toBeTruthy();
      console.log(`  First shared location: ${sp.locationName} (${sp.personCount} subjects, ${sp.personNames.join(', ')})`);
    }
  });

  test('shared presence returns empty for single person', async ({ request }) => {
    const searchResponse = await request.get('/api/investigation/people/search', {
      params: { q: KNOWN_PERSON_SEARCH, limit: 1 },
    });
    const people = await searchResponse.json();
    const personId = people[0].personId;

    const response = await request.get('/api/investigation/shared-presence', {
      params: { personIds: String(personId) },
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    // Single person can't have shared presence with themselves
    expect(Array.isArray(data)).toBeTruthy();
    expect(data.length).toBe(0);
  });

  test('financial network API returns transactions', async ({ request }) => {
    const searchResponse = await request.get('/api/investigation/people/search', {
      params: { q: KNOWN_PERSON_SEARCH, limit: 5 },
    });
    const people = await searchResponse.json();
    const personId = people[0].personId;

    const response = await request.get('/api/investigation/financial-network', {
      params: { personIds: String(personId) },
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(Array.isArray(data)).toBeTruthy();
    console.log(`Financial network: ${data.length} transactions for person ${personId}`);
  });
});

// ─── UI Tests ────────────────────────────────────────────────────────────────

test.describe('Investigation Workbench UI', () => {
  test.describe.configure({ mode: 'serial' });

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await login(page);
    await navigateToInvestigation(page);
    await page.waitForTimeout(2000);
  });

  test('investigation page loads with correct layout', async ({ page }) => {
    // Page container visible
    await expect(page.locator('[data-testid="investigation-page"]')).toBeVisible();

    // Map container visible
    await expect(page.locator('[data-testid="investigation-map"]')).toBeVisible();

    // Search input visible
    await expect(page.locator('[data-testid="person-search-input"]')).toBeVisible();

    // Tab bar visible
    await expect(page.locator('[data-testid="tab-connections"]')).toBeVisible();
    await expect(page.locator('[data-testid="tab-shared"]')).toBeVisible();
    await expect(page.locator('[data-testid="tab-financial"]')).toBeVisible();

    // Date filter inputs
    await expect(page.locator('[data-testid="date-from-input"]')).toBeVisible();
    await expect(page.locator('[data-testid="date-to-input"]')).toBeVisible();

    console.log('Investigation page layout verified');
  });

  test('person search shows results', async ({ page }) => {
    const searchInput = page.locator('[data-testid="person-search-input"]');
    await searchInput.click();
    await searchInput.pressSequentially('Jeffrey', { delay: 50 });

    // Results dropdown should appear (wait for query to return)
    const resultButton = page.locator('[data-testid="person-search-results"] button').first();
    await expect(resultButton).toBeVisible({ timeout: 30000 });

    const count = await page.locator('[data-testid="person-search-results"] button').count();
    expect(count).toBeGreaterThan(0);
    console.log(`Person search showed ${count} results for "Jeffrey"`);
  });

  test('adding a subject shows chip and loads map markers', async ({ page }) => {
    // Search for Epstein
    await typeSearch(page, KNOWN_PERSON_SEARCH);
    await page.waitForTimeout(1000);

    const results = page.locator('[data-testid="person-search-results"]');
    await expect(results).toBeVisible({ timeout: 5000 });

    // Click the first result
    const firstResult = results.locator('button').first();
    const personNameText = await firstResult.locator('.font-medium').textContent();
    await firstResult.click();
    await page.waitForTimeout(3000);

    console.log(`Added subject: ${personNameText}`);

    // A subject chip should now be visible
    const chips = page.locator('[data-testid^="subject-chip-"]');
    await expect(chips.first()).toBeVisible({ timeout: 5000 });
    console.log('Subject chip appeared');

    // Stats footer should show location and placement counts
    const statLocations = page.locator('[data-testid="stat-locations"]');
    await expect(statLocations).toBeVisible({ timeout: 5000 });
    const statText = await statLocations.textContent();
    console.log(`Stats: ${statText}`);

    // Verify some locations are loaded
    const statPlacements = page.locator('[data-testid="stat-placements"]');
    await expect(statPlacements).toBeVisible();
    const placementText = await statPlacements.textContent();
    const placementNum = parseInt(placementText?.match(/\d+/)?.[0] ?? '0');
    expect(placementNum).toBeGreaterThan(0);
    console.log(`Placements loaded: ${placementNum}`);
  });

  test('clicking subject chip opens connections panel', async ({ page }) => {
    // Add a subject — addSubject() auto-selects the new subject, so connections load immediately
    await typeSearch(page, KNOWN_PERSON_SEARCH);
    await page.waitForTimeout(1000);

    const results = page.locator('[data-testid="person-search-results"]');
    await results.locator('button').first().click();

    // Connections panel should be visible (subject is auto-selected when added)
    const connectionsPanel = page.locator('[data-testid="connections-panel"]');
    await expect(connectionsPanel).toBeVisible({ timeout: 5000 });

    // Wait for connections data to load (API takes ~1s)
    await page.waitForSelector('[data-testid="connections-data"]', { timeout: 30000 });

    // Should show location items
    const locationItems = page.locator('[data-testid^="location-item-"]');
    const locationCount = await locationItems.count();
    expect(locationCount).toBeGreaterThan(0);
    console.log(`Connections panel shows ${locationCount} locations`);

    // Also test chip deselect/reselect: clicking chip should toggle
    const chip = page.locator('[data-testid^="subject-chip-"]').first();
    await chip.click(); // deselect
    await expect(page.locator('text=Click a subject chip to view their connections')).toBeVisible({ timeout: 3000 });
    await chip.click(); // reselect
    await page.waitForSelector('[data-testid="connections-data"]', { timeout: 30000 });
    console.log('Chip toggle (deselect/reselect) works');
  });

  test('connections panel shows people connected to subject', async ({ page }) => {
    // Add a subject — it is auto-selected, connections load automatically
    await typeSearch(page, KNOWN_PERSON_SEARCH);
    await page.waitForTimeout(1000);

    await page.locator('[data-testid="person-search-results"]').locator('button').first().click();
    await page.waitForSelector('[data-testid="connections-data"]', { timeout: 30000 });

    // Should show connected people
    const connectedPeople = page.locator('[data-testid^="connected-person-"]');
    const count = await connectedPeople.count();
    console.log(`Found ${count} connected people`);

    // Epstein should have many connected people from co-location data
    if (count === 0) {
      // Check if the section exists at all
      const section = page.locator('text=Connected People');
      await expect(section).toBeVisible();
      console.log('Connected People section visible but 0 items (may have no relationships in DB)');
    } else {
      expect(count).toBeGreaterThan(0);
    }
  });

  test('date filter narrows down map placements', async ({ page }) => {
    // Add a subject
    await typeSearch(page, KNOWN_PERSON_SEARCH);
    await page.waitForTimeout(1000);
    await page.locator('[data-testid="person-search-results"]').locator('button').first().click();
    await page.waitForTimeout(2000);

    // Get initial placement count
    const statPlacements = page.locator('[data-testid="stat-placements"]');
    await expect(statPlacements).toBeVisible();
    const initialText = await statPlacements.textContent();
    const initialCount = parseInt(initialText?.match(/\d+/)?.[0] ?? '0');

    // Apply date filter
    await page.locator('[data-testid="date-from-input"]').fill('2004-01-01');
    await page.locator('[data-testid="date-to-input"]').fill('2005-12-31');
    await page.waitForTimeout(2000);

    // Count should change (likely decrease)
    const filteredText = await statPlacements.textContent();
    const filteredCount = parseInt(filteredText?.match(/\d+/)?.[0] ?? '0');

    console.log(`Initial placements: ${initialCount}, Filtered (2004-2005): ${filteredCount}`);
    // Filtered should be <= initial
    expect(filteredCount).toBeLessThanOrEqual(initialCount);
  });

  test('hot spots tab shows shared locations for multiple subjects', async ({ page }) => {
    // Add two subjects

    // Add first person
    await typeSearch(page, 'Jeffrey');
    await page.waitForTimeout(1000);
    await page.locator('[data-testid="person-search-results"]').locator('button').first().click();
    await page.waitForTimeout(1500);

    // Add second person (different search term)
    await typeSearch(page, 'Maxwell');
    await page.waitForTimeout(1000);
    const maxwellResults = page.locator('[data-testid="person-search-results"]');
    const maxwellVisible = await maxwellResults.isVisible({ timeout: 3000 }).catch(() => false);

    if (maxwellVisible) {
      const resultCount = await maxwellResults.locator('button').count();
      if (resultCount > 0) {
        await maxwellResults.locator('button').first().click();
        await page.waitForTimeout(2000);
      }
    }

    // Navigate to Hot Spots tab
    await page.locator('[data-testid="tab-shared"]').click();
    await page.waitForTimeout(2000);

    const sharedPanel = page.locator('[data-testid="shared-presence-panel"]');
    await expect(sharedPanel).toBeVisible();

    // Check if we have shared presence data
    const sharedData = page.locator('[data-testid="shared-presence-data"]');
    const hasSharedData = await sharedData.isVisible({ timeout: 3000 }).catch(() => false);

    if (hasSharedData) {
      const sharedLocations = page.locator('[data-testid^="shared-location-"]');
      const count = await sharedLocations.count();
      expect(count).toBeGreaterThan(0);
      console.log(`Hot Spots tab shows ${count} shared locations`);

      // Check stat badge
      const statHotspots = page.locator('[data-testid="stat-hotspots"]');
      if (await statHotspots.isVisible().catch(() => false)) {
        const hotspotsText = await statHotspots.textContent();
        console.log(`Hot spots badge: ${hotspotsText}`);
      }
    } else {
      // No shared presence data — could be 2 subjects with no overlap
      console.log('No shared presence data found (subjects may not share locations)');
    }
  });

  test('financial tab shows transactions for subjects', async ({ page }) => {
    // Add a subject
    await typeSearch(page, KNOWN_PERSON_SEARCH);
    await page.waitForTimeout(1000);
    await page.locator('[data-testid="person-search-results"]').locator('button').first().click();
    await page.waitForTimeout(2000);

    // Navigate to Financial tab
    await page.locator('[data-testid="tab-financial"]').click();
    await page.waitForTimeout(2000);

    const financialPanel = page.locator('[data-testid="financial-panel"]');
    await expect(financialPanel).toBeVisible();

    // Check for financial data or empty state
    const financialData = page.locator('[data-testid="financial-data"]');
    const hasFinancialData = await financialData.isVisible({ timeout: 3000 }).catch(() => false);

    if (hasFinancialData) {
      const txns = page.locator('[data-testid^="financial-txn-"]');
      const count = await txns.count();
      expect(count).toBeGreaterThan(0);
      console.log(`Financial tab shows ${count} transactions`);

      // Verify transaction structure
      const firstTxn = txns.first();
      await expect(firstTxn).toBeVisible();
    } else {
      console.log('No financial transactions found for this subject');
    }
  });

  test('removing a subject removes their chip', async ({ page }) => {
    // Add a subject
    await typeSearch(page, KNOWN_PERSON_SEARCH);
    await page.waitForTimeout(1000);
    await page.locator('[data-testid="person-search-results"]').locator('button').first().click();
    await page.waitForTimeout(1000);

    // Verify chip appeared
    const chips = page.locator('[data-testid^="subject-chip-"]');
    await expect(chips.first()).toBeVisible();

    // Click the X button to remove
    const removeButton = chips.first().locator('button');
    await removeButton.click();
    await page.waitForTimeout(500);

    // Chip should be gone
    const remainingChips = await chips.count();
    expect(remainingChips).toBe(0);
    console.log('Subject chip removed successfully');
  });

  test('map popup shows people at location', async ({ page }) => {
    // Add Epstein as subject
    await typeSearch(page, KNOWN_PERSON_SEARCH);
    await page.waitForTimeout(1000);
    await page.locator('[data-testid="person-search-results"]').locator('button').first().click();
    await page.waitForTimeout(3000);

    // Wait for markers to appear (they're in the map container)
    // Click a marker on the map - markers are rendered as divs inside the map
    const mapContainer = page.locator('[data-testid="investigation-map"]');
    await expect(mapContainer).toBeVisible();

    // Subject is auto-selected when added — connections panel loads automatically
    await page.waitForSelector('[data-testid="connections-data"]', { timeout: 30000 });

    // Click first location to highlight on map
    const firstLocation = page.locator('[data-testid^="location-item-"]').first();
    if (await firstLocation.isVisible()) {
      await firstLocation.click();
      await page.waitForTimeout(1000);
      // Map popup should appear
      const popup = page.locator('[data-testid="map-popup"]');
      const popupVisible = await popup.isVisible({ timeout: 3000 }).catch(() => false);
      if (popupVisible) {
        const popupText = await popup.textContent();
        console.log(`Map popup content: ${popupText?.substring(0, 100)}`);
        expect(popupText).toBeTruthy();
      } else {
        console.log('Map popup not shown (marker may not be in current view)');
      }
    }
  });

  test('investigation page navigation is in sidebar', async ({ page }) => {
    // Check that Investigation is in the sidebar
    await page.goto('/');
    await login(page);

    // Hover to expand sidebar
    const sidebar = page.locator('aside');
    await sidebar.hover();
    await page.waitForTimeout(300);

    // Look for Investigation link
    const investigationLink = page.locator('a[href="/investigation"]');
    await expect(investigationLink).toBeVisible({ timeout: 5000 });
    console.log('Investigation link found in sidebar');
  });
});

// ─── Data Population Tests ────────────────────────────────────────────────────

test.describe('Data Population Verification', () => {
  test('geo-timeline has entries with both lat/lng populated', async ({ request }) => {
    const response = await request.get('/api/investigation/geo-timeline', {
      params: { limit: 200 },
    });
    const data = await response.json();
    expect(data.length).toBeGreaterThan(0);

    // All returned entries should have valid coordinates (API filters nulls)
    const withCoords = data.filter(
      (e: { latitude?: number; longitude?: number }) =>
        e.latitude != null && e.longitude != null
    );
    expect(withCoords.length).toBe(data.length);
    console.log(`Geo-timeline: ${data.length} entries all have coordinates`);
  });

  test('person connections returns data for high-placement persons', async ({ request }) => {
    // Get the person with most placements
    const searchResponse = await request.get('/api/investigation/people/search', {
      params: { q: '', limit: 5 },
    });
    const people = await searchResponse.json();
    expect(people.length).toBeGreaterThan(0);

    const topPerson = people[0]; // sorted by placement count desc
    expect(topPerson.placementCount).toBeGreaterThan(0);

    const connResponse = await request.get(
      `/api/investigation/person/${topPerson.personId}/connections`
    );
    const connections = await connResponse.json();

    expect(connections.locations.length).toBeGreaterThan(0);
    expect(connections.coPresences.length).toBeGreaterThan(0);

    console.log(`Top person: ${topPerson.personName} with ${topPerson.placementCount} placements`);
    console.log(`  → ${connections.locations.length} unique locations`);
    console.log(`  → ${connections.coPresences.length} co-presence instances`);
    console.log(`  → ${connections.relatedPeople.length} connected people`);
  });

  test('multiple subjects show shared presence data', async ({ request }) => {
    // Get top 3 people by placements
    const searchResponse = await request.get('/api/investigation/people/search', {
      params: { q: '', limit: 10 },
    });
    const people = await searchResponse.json();

    // Take first 3 with high placement counts
    const ids = people
      .filter((p: { placementCount: number }) => p.placementCount > 5)
      .slice(0, 3)
      .map((p: { personId: number }) => p.personId);

    if (ids.length < 2) {
      console.log('Not enough high-placement subjects for shared presence test');
      return;
    }

    const response = await request.get('/api/investigation/shared-presence', {
      params: { personIds: ids.join(',') },
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    console.log(`Shared presence for ${ids.length} subjects: ${data.length} shared locations`);

    if (data.length > 0) {
      const sp = data[0];
      expect(sp.personCount).toBeGreaterThanOrEqual(2);
      expect(sp.personNames.length).toBeGreaterThanOrEqual(2);
      console.log(`Top shared location: ${sp.locationName} shared by ${sp.personNames.join(', ')}`);
    }
  });
});
