#!/usr/bin/env node
/**
 * Open a visible Chrome window already signed in to an instance, for manual testing
 * (no typing of passwords). The window stays open until you close it.
 *
 *   node tools/open-browser.mjs [url]        default: training dashboard 18
 *   node tools/open-browser.mjs --tour       auto-play every page at every screen size
 *
 * Tour options (all optional):
 *   --speed=4          seconds each screen stays up (default 4)
 *   --sizes=375x667,768x1024,1024x768,1440x900
 *   --order=page|size  page: all sizes of one page, then next page (default); size: all pages at one size
 *   --pages=18,16,welcome,dashlist   only these (dashboard ids or names); default = all known pages
 *   --start=3          start at screen number 3
 *   --base=https://sstraining.habtechsolution.com
 * Controls while touring (terminal, or the buttons in the on-page bar):
 *   space pause/resume   n/right next   p/left previous   + faster   - slower   q quit
 *
 * Credentials: MOH_UI_USER/MOH_UI_PASS, or MOH_UI_CREDS_FILE (default
 * ~/.config/moh-ui-test/training-admin.env), either KEY=VALUE lines or Username:/Password: lines.
 * Never printed. NOTE: the account may have edit rights; look, do not save changes.
 */
import { chromium } from '@playwright/test';
import fs from 'fs';
import os from 'os';
import path from 'path';

const url = process.argv.slice(2).find(a => !a.startsWith('--')) || 'https://sstraining.habtechsolution.com/superset/dashboard/18/';
const origin = new URL(url).origin;

function readCreds() {
  if (process.env.MOH_UI_USER && process.env.MOH_UI_PASS) return { user: process.env.MOH_UI_USER, pass: process.env.MOH_UI_PASS };
  const f = process.env.MOH_UI_CREDS_FILE || path.join(os.homedir(), '.config', 'moh-ui-test', 'training-admin.env');
  if (!fs.existsSync(f)) { console.error('No credentials file: ' + f); process.exit(2); }
  const lines = fs.readFileSync(f, 'utf8').split('\n').map(l => l.trim()).filter(Boolean);
  const kv = Object.fromEntries(lines.map(l => l.match(/^(MOH_UI_USER|MOH_UI_PASS)=(.*)$/)).filter(Boolean).map(m => [m[1], m[2]]));
  if (kv.MOH_UI_USER && kv.MOH_UI_PASS) return { user: kv.MOH_UI_USER, pass: kv.MOH_UI_PASS };
  const at = re => { const i = lines.findIndex(l => re.test(l)); return i >= 0 ? lines[i + 1] : undefined; };
  const user = at(/^username:?$/i), pass = at(/^password:?$/i);
  if (!user || !pass) { console.error('Unrecognised credentials format in ' + f); process.exit(2); }
  return { user, pass };
}

const args = process.argv.slice(2);
const flag = n => { const a = args.find(x => x.startsWith('--' + n + '=')); return a ? a.split('=').slice(1).join('=') : undefined; };
const tour = args.includes('--tour');
const { user, pass } = readCreds();
const browser = await chromium.launch({ channel: 'chrome', headless: false, args: tour ? [] : ['--auto-open-devtools-for-tabs'] });
const context = await browser.newContext({ viewport: tour ? { width: 1440, height: 900 } : null });
const page = await context.newPage();
await page.goto(origin + '/login/', { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.fill('#username', user);
await page.fill('#password', pass);
await page.click('button[type=submit], input[type=submit]');
await page.waitForURL(u => !/\/login\//.test(u.toString()), { timeout: 30000 }).catch(() => {
  console.error('Login failed'); process.exit(2);
});
browser.on('disconnected', () => process.exit(0));

if (!tour) {
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  console.log('Signed in; Chrome is open at ' + url + '. Close the window when you are done.');
  await new Promise(() => {});
}

// ---- tour ----
const base = flag('base') || origin;
const sizes = (flag('sizes') || '375x667,768x1024,1024x768,1440x900').split(',').map(s => s.split('x').map(Number));
let speed = Number(flag('speed') || 4);
const STATIC = [['welcome', '/superset/welcome/'], ['dashlist', '/dashboard/list/'], ['chartlist', '/chart/list/'],
  ['guide', '/guide/'], ['feedback', '/feedback/'], ['ai-chat', '/ai-chat/'], ['tv', '/moh-static/tv']];
let pages = [...STATIC];
try { // dashboards (and their tabs) discovered by the test suite, if it has run
  const f = path.join(path.dirname(new URL(import.meta.url).pathname), '..', '.auth', 'training.dashboards.json');
  for (const d of JSON.parse(fs.readFileSync(f, 'utf8'))) {
    pages.push(['dash' + d.id, `/superset/dashboard/${d.id}/`]);
    [1, 4, 5].forEach(n => d.tabs[n - 1] && pages.push([`dash${d.id}-tab${n}`, `/superset/dashboard/${d.id}/#${d.tabs[n - 1]}`]));
  }
} catch {
  for (const id of [18, 16, 17, 15, 1]) pages.push(['dash' + id, `/superset/dashboard/${id}/`]);
}
const only = flag('pages');
if (only) {
  const want = only.split(',').map(s => s.trim());
  pages = pages.filter(([id]) => want.some(w => id === w || id === 'dash' + w || id.startsWith('dash' + w + '-')));
}
const order = flag('order') || 'page';
const steps = [];
if (order === 'size') for (const sz of sizes) for (const pg of pages) steps.push({ pg, sz });
else for (const pg of pages) for (const sz of sizes) steps.push({ pg, sz });
if (!steps.length) { console.error('No pages matched --pages'); process.exit(2); }

let i = Math.max(0, Number(flag('start') || 1) - 1), paused = false, jump = 0, quit = false;
const nudge = d => { jump = d; };
await page.exposeFunction('__tour', c => ({ pause: () => (paused = !paused), next: () => nudge(1), prev: () => nudge(-1),
  faster: () => (speed = Math.max(1, speed - 1)), slower: () => (speed += 1), quit: () => (quit = true) }[c]?.()));
const HUD = `(() => {
  if (document.getElementById('__tourbar')) return;
  const b = document.createElement('div'); b.id = '__tourbar';
  b.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:2147483647;background:#111;color:#fff;font:12px/1.2 sans-serif;padding:4px 6px;display:flex;gap:4px;flex-wrap:wrap;align-items:center;opacity:.92';
  b.innerHTML = '<span id="__tourtxt" style="flex:1 1 100%"></span>' + [['prev','◀'],['pause','⏯'],['next','▶'],['faster','+'],['slower','−'],['quit','✕']]
    .map(([c,t]) => '<button data-c="'+c+'" style="font:14px sans-serif;padding:2px 10px;min-width:36px">'+t+'</button>').join('');
  b.onclick = e => { const c = e.target.dataset && e.target.dataset.c; if (c) window.__tour(c); };
  document.documentElement.appendChild(b);
})()`;
const label = t => page.evaluate(`(()=>{const e=document.getElementById('__tourtxt'); if(e) e.textContent=${JSON.stringify(t)}})()`).catch(() => {});

if (process.stdin.isTTY) {
  process.stdin.setRawMode(true); process.stdin.resume();
  process.stdin.on('data', k => {
    const c = k.toString();
    if (c === ' ') paused = !paused; else if (c === 'n' || c === '\u001b[C') nudge(1); else if (c === 'p' || c === '\u001b[D') nudge(-1);
    else if (c === '+' || c === '=') speed = Math.max(1, speed - 1); else if (c === '-') speed += 1;
    else if (c === 'q' || c === '\u0003') quit = true;
  });
}
console.log(`Tour: ${steps.length} screens, ${speed}s each. space=pause n=next p=prev +=faster -=slower q=quit`);
while (!quit && i < steps.length) {
  const { pg: [id, p], sz: [w, h] } = steps[i];
  const tag = `${i + 1}/${steps.length}  ${id}  ${w}x${h}`;
  await page.setViewportSize({ width: w, height: h });
  await page.goto(base + p, { waitUntil: 'domcontentloaded' }).catch(() => {});
  if (p.includes('#')) await page.reload({ waitUntil: 'domcontentloaded' }).catch(() => {});
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
  await page.evaluate(HUD).catch(() => {});
  console.log(tag);
  jump = 0;
  for (let t = 0; !quit && !jump && (paused || t < speed * 10); t += paused ? 0 : 1) {
    await label(`${tag}  ·  ${paused ? 'PAUSED' : speed + 's'}`);
    await new Promise(r => setTimeout(r, 100));
  }
  i = jump ? Math.min(steps.length - 1, Math.max(0, i + jump)) : i + 1;
}
console.log('Tour finished.');
await browser.close();
process.exit(0);
