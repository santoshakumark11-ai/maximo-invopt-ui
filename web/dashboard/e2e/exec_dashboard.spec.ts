/**
 * Playwright E2E — Executive Dashboard smoke test.
 *
 * Runs against the dev server with VITE_USE_MSW=true so no real backend
 * is required.  Start the server before running:
 *
 *   pnpm dev
 *
 * Then in another terminal:
 *
 *   pnpm exec playwright test
 */
import { test, expect } from '@playwright/test';

const BASE = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:5173';

test.describe('Executive Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(BASE);
  });

  test('page title is correct', async ({ page }) => {
    await expect(page).toHaveTitle(/Inventory Optimisation Agent/i);
  });

  test('renders KPI strip with four cards', async ({ page }) => {
    const cards = page.getByTestId('kpi-card');
    await expect(cards).toHaveCount(4);
  });

  test('shows MSW fixture inventory value', async ({ page }) => {
    // MSW fixture: inventoryValue = 4_820_000 → "$4.8M"
    await expect(page.getByText('$4.8M')).toBeVisible();
  });

  test('shows MSW fixture service level', async ({ page }) => {
    await expect(page.getByText('97.4%')).toBeVisible();
  });

  test('working capital chart is visible', async ({ page }) => {
    await expect(page.getByTestId('working-capital-chart')).toBeVisible();
  });

  test('recommendations donut chart is visible', async ({ page }) => {
    await expect(page.getByTestId('recs-by-status-chart')).toBeVisible();
  });

  test('forecast accuracy table is visible', async ({ page }) => {
    await expect(page.getByTestId('forecast-accuracy-table')).toBeVisible();
  });

  test('top items table is visible', async ({ page }) => {
    await expect(page.getByTestId('top-items-table')).toBeVisible();
  });

  test('404 page shown for unknown route', async ({ page }) => {
    await page.goto(`${BASE}/unknown-route`);
    await expect(page.getByTestId('not-found')).toBeVisible();
    await expect(page.getByText('404')).toBeVisible();
  });
});
