import { chromium, FullConfig } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { BASE_URL, STATE_FILE, credentials } from './env';

/**
 * Logs in once (read-only account), saves the session, and discovers every
 * dashboard (and its tabs) the account can see so "test all" really is all.
 */
export default async function globalSetup(config: FullConfig) {
  const { user, pass } = credentials();
  fs.mkdirSync(path.dirname(STATE_FILE), { recursive: true });
  const browser = await chromium.launch({
    channel: process.env.MOH_UI_CHANNEL || undefined,
  });
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  // Log in (up to 3 attempts: a single network blip must not fail a deploy gate).
  let authed = false;
  for (let attempt = 1; attempt <= 3 && !authed; attempt++) {
    try {
      await page.goto(`${BASE_URL}/login/`, { waitUntil: 'domcontentloaded', timeout: 60_000 });
      await page.fill('#username', user);
      await page.fill('#password', pass);
      await page.click('input[type=submit],button[type=submit]');
      await page.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 30_000 });
      await page.waitForLoadState('domcontentloaded');
      // The URL changes before the session cookie is usable by fetch(); wait for it.
      for (let i = 0; i < 20 && !authed; i++) {
        authed = await page.evaluate(async () => (await fetch('/api/v1/me/')).status === 200);
        if (!authed) await page.waitForTimeout(1500);
      }
    } catch (e) {
      console.log(`[moh-ui] login attempt ${attempt} failed: ${(e as Error).message.split('\n')[0]}`);
    }
  }
  if (!authed) throw new Error('Login did not produce an authenticated session (/api/v1/me/ not 200)');

  type Dash = { id: number; title: string; tabs: string[] };
  const discover = () =>
    page.evaluate(async () => {
      const q = encodeURIComponent(
        JSON.stringify({ page_size: 100, columns: ['id', 'dashboard_title'] }),
      );
      const r = await fetch(`/api/v1/dashboard/?q=${q}`);
      if (!r.ok) return { status: r.status, items: [] as Dash[] };
      const j = await r.json();
      const items: Dash[] = [];
      for (const d of j.result || []) {
        let tabs: string[] = [];
        try {
          const dr = await fetch(`/api/v1/dashboard/${d.id}`);
          const dj = await dr.json();
          const pos = JSON.parse(dj.result?.position_json || '{}');
          tabs = Object.keys(pos).filter(k => k.startsWith('TAB-')).slice(0, 8);
        } catch (e) {
          /* tabs are best effort */
        }
        items.push({ id: d.id, title: d.dashboard_title, tabs });
      }
      return { status: r.status, items };
    });
  let found = await discover();
  for (let i = 0; i < 3 && found.items.length === 0; i++) {
    await page.waitForTimeout(5000);
    found = await discover();
  }
  const dashboards = found.items;
  // A silent empty discovery would shrink the test set and let regressions
  // through, so it is an error unless explicitly allowed.
  if (dashboards.length === 0 && process.env.MOH_UI_ALLOW_NO_DASHBOARDS !== '1') {
    throw new Error(
      `Dashboard discovery returned 0 dashboards (API status ${found.status}); refusing to run with reduced coverage`,
    );
  }
  fs.writeFileSync(
    path.join(path.dirname(STATE_FILE), `${process.env.MOH_UI_TARGET || 'prod'}.dashboards.json`),
    JSON.stringify(dashboards, null, 1),
  );
  await ctx.storageState({ path: STATE_FILE });
  fs.chmodSync(STATE_FILE, 0o600);
  await browser.close();
  console.log(`[moh-ui] logged in; ${dashboards.length} dashboard(s) discovered`);
}
