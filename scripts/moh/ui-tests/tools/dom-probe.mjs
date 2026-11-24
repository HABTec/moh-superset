#!/usr/bin/env node
/** Print the (truncated) outerHTML + box + computed role info of the first N matches of selectors, on a signed-in page.
 *   node tools/dom-probe.mjs <path> <width> <selector> [<selector> ...]      env: BASE, N (default 2), WAIT (ms, default 7000)
 * Credentials as in open-browser.mjs (MOH_UI_USER/PASS or MOH_UI_CREDS_FILE or ~/.config/moh-ui-test/training-admin.env). Read-only. */
import { chromium } from '@playwright/test'; import fs from 'fs'; import os from 'os'; import path from 'path';
const [p, w, ...sels] = process.argv.slice(2); const BASE = process.env.BASE || 'https://sstraining.habtechsolution.com';
function creds() { if (process.env.MOH_UI_USER) return [process.env.MOH_UI_USER, process.env.MOH_UI_PASS];
  const f = process.env.MOH_UI_CREDS_FILE || path.join(os.homedir(), '.config/moh-ui-test/training-admin.env'); const L = fs.readFileSync(f, 'utf8').split('\n').map(s => s.trim()).filter(Boolean);
  const kv = Object.fromEntries(L.map(l => l.match(/^(MOH_UI_USER|MOH_UI_PASS)=(.*)$/)).filter(Boolean).map(m => [m[1], m[2]])); if (kv.MOH_UI_USER) return [kv.MOH_UI_USER, kv.MOH_UI_PASS];
  const at = r => L[L.findIndex(l => r.test(l)) + 1]; return [at(/^username:?$/i), at(/^password:?$/i)]; }
const [u, pw] = creds(); const b = await chromium.launch({ channel: process.env.MOH_UI_CHANNEL || 'chrome' }); const pg = await (await b.newContext()).newPage();
await pg.goto(BASE + '/login/'); await pg.fill('#username', u); await pg.fill('#password', pw); await pg.click('button[type=submit],input[type=submit]'); await pg.waitForURL(x => !/login/.test(x.toString()));
await pg.setViewportSize({ width: +w, height: +w < 500 ? 800 : 900 }); await pg.goto(BASE + p, { waitUntil: 'domcontentloaded' }); await pg.waitForLoadState('networkidle', { timeout: 20000 }).catch(() => {}); if (process.env.WAITFOR) await pg.waitForSelector(process.env.WAITFOR, { timeout: 40000 }).catch(() => console.log('WAITFOR timed out')); await pg.waitForTimeout(+(process.env.WAIT || 7000));
for (const s of sels) { const r = await pg.evaluate(([s, n]) => { const all = [...document.querySelectorAll(s)]; return { count: all.length, items: all.slice(0, n).map(e => { const r = e.getBoundingClientRect(); return { box: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)], html: e.outerHTML.slice(0, 420), parent: e.parentElement && e.parentElement.outerHTML.slice(0, 160) }; }) }; }, [s, +(process.env.N || 2)]);
  console.log('\n### ' + s + '  (' + r.count + ' matches)'); r.items.forEach(i => console.log(JSON.stringify(i))); }
await b.close();
