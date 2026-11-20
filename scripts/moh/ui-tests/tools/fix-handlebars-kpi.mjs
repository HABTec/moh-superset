/**
 * Raise the contrast and minimum size of KPI-card text stored in Handlebars chart
 * definitions (clamp(8..10px) -> 11px min; #6b7280 -> #4b5563). This is a CONTENT
 * change to chart definitions in the database, so it needs an owner/admin account:
 * the read-only test account gets 403.
 *
 * Needs: backups of the current params in /var/tmp/moh-a11y-chart-backup-<target>/<id>.json
 * (written by the dump step) and a logged-in storage state with edit rights
 * (.auth/<target>.json produced by running the suite with that account's MOH_UI_USER/PASS).
 * DRY=1 prints before/after without writing. Usage: node fix-handlebars-kpi.mjs all|<id...>
 */
import {chromium} from '@playwright/test';
import fs from 'fs';
const BK='/var/tmp/moh-a11y-chart-backup-training';
const ids = process.argv[2]==='all' ? fs.readdirSync(BK).map(f=>+f.replace('.json','')) : process.argv.slice(2).map(Number);
const DRY = process.env.DRY==='1';
const MAP = [
  [/font-size:\s*clamp\(8px,\s*1\.4vh,\s*10px\)/gi, 'font-size:clamp(11px,1.4vh,12px)'],
  [/font-size:\s*clamp\(8px,\s*1\.4vh,\s*11px\)/gi, 'font-size:clamp(11px,1.4vh,12px)'],
  [/font-size:\s*clamp\(9px,\s*1\.6vh,\s*11px\)/gi, 'font-size:clamp(11px,1.6vh,12px)'],
  [/font-size:\s*clamp\(10px,\s*2vh,\s*13px\)/gi, 'font-size:clamp(11px,2vh,13px)'],
  [/font-size:\s*clamp\(10px,\s*2vh,\s*14px\)/gi, 'font-size:clamp(11px,2vh,14px)'],
  [/color:\s*#6b7280/gi, 'color:#4b5563'],
];
const b = await chromium.launch({channel:'chrome'});
const c = await b.newContext({storageState: '../.auth/training.json'});
const base='https://sstraining.habtechsolution.com';
const csrf = (await (await c.request.get(base+'/api/v1/security/csrf_token/')).json()).result;
let ok=0, fail=0;
for (const id of ids) {
  const orig = JSON.parse(fs.readFileSync(`${BK}/${id}.json`,'utf8'));
  const p = JSON.parse(orig.params);
  const key = 'handlebarsTemplate' in p ? 'handlebarsTemplate' : 'handlebars_template';
  const before = p[key]; let after = before;
  for (const [re, to] of MAP) after = after.replace(re, to);
  const changed = before !== after;
  if (!changed) { console.log(id,'no change'); continue; }
  p[key] = after;
  if (DRY || process.env.SHOW) console.log(id, orig.slice_name, '\n  BEFORE', (before.match(/font-size:\s*clamp\([^)]*\)|color:\s*#6b7280/gi)||[]).slice(0,4).join(' | '), '\n  AFTER ', (after.match(/font-size:\s*clamp\([^)]*\)|color:\s*#4b5563/gi)||[]).slice(0,4).join(' | '));
  if (DRY) continue;
  const r = await c.request.put(base+`/api/v1/chart/${id}`, {headers:{'X-CSRFToken':csrf,'Referer':base+'/','Content-Type':'application/json'}, data:{params: JSON.stringify(p)}});
  if (r.status()===200) { ok++; } else { fail++; console.log(id,'FAILED',r.status(),(await r.text()).slice(0,200)); }
}
console.log({ok,fail});
await b.close();
