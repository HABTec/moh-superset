import { test, expect } from '@playwright/test';
import { discoveredDashboards } from '../lib/pages';

/**
 * Functional smoke tests: the features must keep working while the layout
 * and accessibility code changes. Read-only: no saves, no deletes, no sends.
 */
test.describe('smoke', () => {
  test('home is reachable after login and shows the portal menu', async ({ page }) => {
    await page.goto('/superset/welcome/');
    await expect(page.getByRole('navigation', { name: /portal|main/i }).first()).toBeVisible();
    await expect(page).not.toHaveURL(/\/login/);
  });

  test('landing page links to dashboards', async ({ page }) => {
    await page.goto('/');
    const links = page.locator('a[href*="/dashboard/"]');
    await expect.poll(() => links.count(), { timeout: 20_000 }).toBeGreaterThan(0);
  });

  test('dashboard list shows every discovered dashboard', async ({ page }) => {
    const dashboards = discoveredDashboards();
    expect(dashboards.length).toBeGreaterThan(0);
    await page.goto('/dashboard/list/');
    // Mobile blocking overlay must not stop the list from existing in the DOM.
    for (const d of dashboards) {
      await expect(page.getByText(d.title.trim(), { exact: false }).first()).toBeAttached({ timeout: 20_000 });
    }
  });

  test('chart list loads', async ({ page }) => {
    await page.goto('/chart/list/');
    await expect(page.locator('main, [role=main]').first()).toBeVisible();
  });

  for (const d of discoveredDashboards()) {
    test(`dashboard ${d.id} opens and renders charts`, async ({ page }) => {
      await page.goto(`/superset/dashboard/${d.id}/`);
      const holders = page.locator('[data-test="dashboard-component-chart-holder"], .dashboard-component-chart-holder');
      await expect.poll(() => holders.count(), { timeout: 45_000 }).toBeGreaterThan(0);
      // at least one chart produced visible output (canvas, svg, table or big number)
      await expect
        .poll(
          () => page.locator('.dashboard-chart canvas, .dashboard-chart svg, .dashboard-chart table, .superset-legacy-chart-big-number, [data-test="chart-container"] canvas, [data-test="chart-container"] svg').count(),
          { timeout: 60_000 },
        )
        .toBeGreaterThan(0);
    });

    test(`dashboard ${d.id} data API answers`, async ({ page }) => {
      await page.goto('/');
      const status = await page.evaluate(async id => (await fetch(`/api/v1/dashboard/${id}/charts`)).status, d.id);
      expect(status).toBe(200);
    });
  }

  test('dashboard filter bar is available where filters exist', async ({ page }) => {
    const d = discoveredDashboards()[0];
    test.skip(!d, 'no dashboards');
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`/superset/dashboard/${d.id}/`);
    await expect
      .poll(() => page.locator('[data-test="filter-bar"], [data-test="filter-bar__expand-button"], [data-test="filterbar-action-buttons"]').count(), { timeout: 45_000 })
      .toBeGreaterThan(0);
  });

  test('TV player loads (not blank)', async ({ page }) => {
    const resp = await page.goto('/moh-static/tv');
    expect(resp?.status()).toBeLessThan(400);
    await page.waitForTimeout(4000);
    expect((await page.locator('body').innerText()).length + (await page.locator('iframe,canvas,svg').count())).toBeGreaterThan(0);
  });

  test('feedback page loads', async ({ page }) => {
    const resp = await page.goto('/feedback/');
    expect(resp?.status()).toBeLessThan(400);
    await expect(page.locator('main, [role=main], form').first()).toBeVisible();
  });

  test('user guide loads', async ({ page }) => {
    const resp = await page.goto('/guide/');
    expect(resp?.status()).toBeLessThan(400);
    await expect(page.locator('main, [role=main]').first()).toBeVisible();
  });

  test('mobile: dashboard is usable at 375px (blocker can be dismissed or absent)', async ({ browser }) => {
    const d = discoveredDashboards()[0];
    test.skip(!d, 'no dashboards');
    const ctx = await browser.newContext({ viewport: { width: 375, height: 667 }, storageState: require('../lib/env').STATE_FILE, hasTouch: true, ignoreHTTPSErrors: true });
    const page = await ctx.newPage();
    await page.goto(`/superset/dashboard/${d.id}/`);
    await page.waitForTimeout(5000);
    const cont = page.getByRole('button', { name: /continue in portrait/i });
    if (await cont.count()) await cont.click();
    await expect(page.locator('[data-test="dashboard-component-chart-holder"], .dashboard-component-chart-holder').first()).toBeVisible({ timeout: 45_000 });
    await ctx.close();
  });
});
