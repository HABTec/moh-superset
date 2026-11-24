#!/usr/bin/env node
/** Run axe on one signed-in page and print, per rule, the failing nodes with their evidence (colours, messages).
 *   node tools/axe-detail.mjs <path> <width> [rule,rule,...]      env: BASE, WAITFOR (selector), WAIT (ms), N (nodes per rule, default 6)
 * Credentials as in dom-probe.mjs. Read-only. */
import { chromium } from '@playwright/test'; import AxeBuilder from '@axe-core/playwright'; import fs from 'fs'; import os from 'os'; import path from 'path';
const [p, w, rules] = process.argv.slice(2); const BASE = process.env.BASE || 'https://sstraining.habtechsolution.com';
function creds() { if (process.env.MOH_UI_USER) return [process.env.MOH_UI_USER, process.env.MOH_UI_PASS];
  const f = process.env.MOH_UI_CREDS_FILE || path.join(os.homedir(), '.config/moh-ui-test/training-admin.env'); const L = fs.readFileSync(f, 'utf8').split('\n').map(s => s.trim()).filter(Boolean);
  const kv = Object.fromEntries(L.map(l => l.match(/^(MOH_UI_USER|MOH_UI_PASS)=(.*)$/)).filter(Boolean).map(m => [m[1], m[2]])); if (kv.MOH_UI_USER) return [kv.MOH_UI_USER, kv.MOH_UI_PASS];
  const at = r => L[L.findIndex(l => r.test(l)) + 1]; return [at(/^username:?$/i), at(/^password:?$/i)]; }
const [u, pw] = creds(); const b = await chromium.launch({ channel: process.env.MOH_UI_CHANNEL || 'chrome' }); const pg = await (await b.newContext()).newPage();
await pg.goto(BASE + '/login/'); await pg.fill('#username', u); await pg.fill('#password', pw); await pg.click('button[type=submit],input[type=submit]'); await pg.waitForURL(x => !/login/.test(x.toString()));
await pg.setViewportSize({ width: +w, height: +w < 500 ? 800 : 900 }); await pg.goto(BASE + p, { waitUntil: 'domcontentloaded' }); if (p.includes('#')) await pg.reload({ waitUntil: 'domcontentloaded' });
if (process.env.WAITFOR) await pg.waitForSelector(process.env.WAITFOR, { state: 'attached', timeout: 60000 }).catch(() => console.log('WAITFOR timed out'));
await pg.waitForTimeout(+(process.env.WAIT || 15000));
for (let y = 0; y < 6000; y += 600) { await pg.evaluate(y => { window.scrollTo(0, y); document.querySelectorAll('*').forEach(e => { if (e.scrollHeight > e.clientHeight + 50 && /auto|scroll/.test(getComputedStyle(e).overflowY)) e.scrollTop = y; }); }, y); await pg.waitForTimeout(300); }
await pg.waitForTimeout(3000);
let ab = new AxeBuilder({ page: pg }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice']); if (rules) ab = ab.withRules(rules.split(','));
const r = await ab.analyze(); const N = +(process.env.N || 6);
for (const v of r.violations) { console.log(`\n## ${v.id} (${v.impact}) x${v.nodes.length}  ${v.help}`);
  for (const n of v.nodes.slice(0, N)) { const c = [...n.any, ...n.all, ...n.none][0] || {}; const d = c.data || {}; const ev = d.fgColor ? `fg ${d.fgColor} bg ${d.bgColor} ratio ${d.contrastRatio} ${d.fontSize}` : (c.message || '').slice(0, 110);
    console.log('  ' + n.target.join(' ').slice(0, 95) + '  | ' + ev + '  | ' + n.html.replace(/\s+/g, ' ').slice(0, 90)); } }
await b.close();
