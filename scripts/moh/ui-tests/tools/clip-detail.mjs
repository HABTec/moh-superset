#!/usr/bin/env node
/** List charts whose canvas/svg/table is wider than its container, with chart id, viz class and the overflow in px.
 *   node tools/clip-detail.mjs <path> <width>      env: BASE, WAIT, MOH_UI_CREDS_FILE   Read-only. */
import { chromium } from '@playwright/test'; import fs from 'fs'; import os from 'os'; import path from 'path';
const [p, w] = process.argv.slice(2); const BASE = process.env.BASE || 'https://sstraining.habtechsolution.com';
const f = process.env.MOH_UI_CREDS_FILE || path.join(os.homedir(), '.config/moh-ui-test/training-admin.env'); const L = fs.readFileSync(f, 'utf8').split('\n').map(s => s.trim()).filter(Boolean); const at = r => L[L.findIndex(l => r.test(l)) + 1];
const b = await chromium.launch({ channel: 'chrome' }); const pg = await (await b.newContext()).newPage();
for (let i = 0; i < 3; i++) { try { await pg.goto(BASE + '/login/', { timeout: 60000 }); break; } catch {} }
await pg.fill('#username', at(/^username:?$/i)); await pg.fill('#password', at(/^password:?$/i)); await pg.click('button[type=submit],input[type=submit]'); await pg.waitForURL(x => !/login/.test(x.toString()));
await pg.setViewportSize({ width: +w, height: +w < 500 ? 800 : 900 }); await pg.goto(BASE + p, { waitUntil: 'domcontentloaded' }); if (p.includes('#')) await pg.reload({ waitUntil: 'domcontentloaded' });
await pg.waitForTimeout(+(process.env.WAIT || 20000));
for (let y = 0; y < 8000; y += 500) { await pg.evaluate(y => { window.scrollTo(0, y); document.querySelectorAll('*').forEach(e => { if (e.scrollHeight > e.clientHeight + 50 && /auto|scroll/.test(getComputedStyle(e).overflowY)) e.scrollTop = y; }); }, y); await pg.waitForTimeout(400); }
await pg.waitForTimeout(4000);
const out = await pg.evaluate(() => { const res = []; for (const c of document.querySelectorAll('canvas,[data-test="chart-container"] svg,table')) {
  const h = c.closest('[data-test="chart-container"],.chart-container,[data-test="dashboard-component-chart-holder"]'); if (!h) continue; const cr = c.getBoundingClientRect(), hr = h.getBoundingClientRect(); if (!cr.width) continue;
  const over = Math.round(cr.right - hr.right); if (over > 4) { const holder = c.closest('[data-test-chart-id]'); res.push({ tag: c.tagName.toLowerCase(), over, canvas: Math.round(cr.width), box: Math.round(hr.width), chart: holder && holder.getAttribute('data-test-chart-id'), viz: (c.closest('[class*="viz"],.slice_container') || {}).className ? (c.closest('.slice_container').firstElementChild || {}).className : '', name: (holder && (holder.querySelector('[data-test="editable-title"],.header-title') || {}).textContent || '').slice(0, 40) }); } } return res; });
console.log(JSON.stringify(out, null, 0).replace(/\},\{/g, '},\n{')); await b.close();
