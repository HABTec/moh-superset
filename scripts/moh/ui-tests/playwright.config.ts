import { defineConfig } from '@playwright/test';
import { BASE_URL, STATE_FILE } from './lib/env';

/**
 * Read-only UI tests for a running MoH Superset instance.
 *   MOH_UI_TARGET     prod | training     (selects budget + credentials)
 *   MOH_UI_BASE_URL   https://...         (instance under test)
 *   MOH_UI_PROFILE    full | gate         (viewport/page coverage, see lib/pages.ts)
 *   MOH_UI_CHANNEL    chrome | (unset)    (use system Chrome instead of bundled Chromium)
 */
export default defineConfig({
  testDir: './tests',
  globalSetup: './lib/global-setup.ts',
  globalTeardown: './lib/global-teardown.ts',
  timeout: 180_000,
  expect: { timeout: 10_000 },
  fullyParallel: true, // tests are independent; concurrency is set by MOH_UI_WORKERS
  workers: Number(process.env.MOH_UI_WORKERS || 1), // production: keep this at 1-2
  retries: 1,
  reporter: [['list'], ['json', { outputFile: 'results/last-run.json' }]],
  use: {
    baseURL: BASE_URL,
    storageState: STATE_FILE,
    ignoreHTTPSErrors: true,
    channel: process.env.MOH_UI_CHANNEL || undefined,
    trace: 'off',
  },
});
