import { test, expect } from '@playwright/test';
test('renders four KPI cards on first paint', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByLabel(/working capital/i)).toBeVisible();
  await expect(page.getByLabel(/open recommendations/i)).toBeVisible();
  await expect(page.getByLabel(/forecast accuracy/i)).toBeVisible();
  await expect(page.getByLabel(/stock-out risks/i)).toBeVisible();
});
