import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { BUDGET_FILE, RESULTS_DIR, STATE_FILE } from '../lib/env';
import { pagesForProfile, viewportsFor } from '../lib/pages';
import { probeStable as probe, Counts } from '../lib/probes';

/**
 * Responsive + accessibility ratchet.
 *
 * For every page x viewport we count issues (see lib/probes.ts for the
 * identifiers) and compare with budgets/<target>.json:
 *   - an issue count may never go UP (small tolerance on noisy counters),
 *   - SEVERE issues are never allowed on a page that has no budget entry,
 *   - fixing issues is welcome: run `npm run budget:update` and commit the
 *     lower numbers (reviewed in the PR) to lock the improvement in.
 * Never raise a budget number to make a failing run pass; fix the page.
 */
const UPDATE = ['1', 'max'].includes(process.env.MOH_UI_UPDATE_BUDGET || ''); // teardown writes the budget
const SEVERE = new Set([
  'RESP-OVERFLOW-X', 'RESP-BLOCKER', 'RESP-CHART-CLIP', 'RESP-TABLE-CLIP',
  'button-name', 'aria-required-children', 'aria-required-parent', 'image-alt',
  'label', 'aria-hidden-focus', 'aria-input-field-name',
]);
const EXACT = new Set(['RESP-OVERFLOW-X', 'RESP-BLOCKER', 'RESP-CHART-CLIP', 'RESP-TABLE-CLIP']);

type Budget = Record<string, Counts>;
const budget: Budget = fs.existsSync(BUDGET_FILE)
  ? JSON.parse(fs.readFileSync(BUDGET_FILE, 'utf8'))
  : {};

// Recorded and reported, never gated: depends on server timing, not on the page.
const NOT_GATED = new Set(['PERF-STUCK-LOADER']);

function allowed(id: string, base: number): number {
  if (EXACT.has(id)) return base;
  if (SEVERE.has(id)) return base; // severe rules never get slack
  // live content wobbles by a few nodes between identical runs: 10% or 2, whichever is more
  return base + Math.max(2, Math.ceil(base * 0.1));
}

for (const pg of pagesForProfile()) {
  for (const [w, h] of viewportsFor(pg)) {
    const key = `${pg.id}@${w}`;
    test(`ui-quality ${key}`, async ({ browser }, info) => {
      test.setTimeout(420_000);
      // Measure only a stably rendered page; reload once if it never settles if it never settles.
      let r;
      for (let attempt = 1; attempt <= 2; attempt++) {
        const ctx = await browser.newContext({
          viewport: { width: w, height: h },
          storageState: pg.id === 'login' ? undefined : STATE_FILE,
          ignoreHTTPSErrors: true,
          hasTouch: w < 1000,
        });
        const page = await ctx.newPage();
        try {
          await page.goto(pg.path, { waitUntil: 'domcontentloaded', timeout: 60_000 });
          r = await probe(page, !!pg.tv);
          fs.mkdirSync(path.join(RESULTS_DIR, 'shots'), { recursive: true });
          await page.screenshot({ path: path.join(RESULTS_DIR, 'shots', `${pg.id}_${w}.png`) });
        } finally {
          await ctx.close();
        }
        if (!r.loadTimeout) break;
      }
      // one file per test: safe with several workers; global-teardown merges them
      fs.mkdirSync(path.join(RESULTS_DIR, 'items'), { recursive: true });
      fs.writeFileSync(
        path.join(RESULTS_DIR, 'items', `${key}.json`),
        JSON.stringify({ key, counts: r!.counts, samples: r!.samples, fixedCoverPct: r!.fixedCoverPct, loadTimeout: r!.loadTimeout, renderMs: r!.renderMs }),
      );
      if (UPDATE) return;
      // Never treat an unrendered page as a pass: this is NOT VERIFIED, reported as a failure.
      // A page that never settles is NOT VERIFIED, unless its budget says it was already like that.
      if (r!.loadTimeout && !(budget[key] && budget[key]._unstable)) {
        expect.soft(false, `NOT VERIFIED: ${key} never reached a stable render in 2 attempts (slow page or server?)`).toBe(true);
      }

      const base = budget[key];
      const problems: string[] = [];
      for (const [id, n] of Object.entries(r!.counts)) {
        if (id.startsWith('_') || NOT_GATED.has(id)) continue;
        if (!base) {
          if (SEVERE.has(id)) problems.push(`${id}: ${n} on a page with no budget (severe issues are never allowed)`);
          continue;
        }
        const max = allowed(id, base[id] ?? 0);
        if (n > max) {
          problems.push(`${id}: ${n} > budget ${base[id] ?? 0} (e.g. ${(r!.samples[id] || []).join(' | ')})`);
        }
      }
      if (!base) info.annotations.push({ type: 'no-budget', description: `${key} has no budget entry; run budget:update` });
      expect(problems, `UI regressions on ${key}:\n  ${problems.join('\n  ')}`).toEqual([]);
    });
  }
}
