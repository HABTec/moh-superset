import fs from 'fs';
import path from 'path';
import { BUDGET_FILE, RESULTS_DIR, TARGET } from './env';

/** Merge the per-test result files into ui-quality.json (always) and the budget (update mode). */
export default async function globalTeardown() {
  const dir = path.join(RESULTS_DIR, 'items');
  if (!fs.existsSync(dir)) return;
  const items = fs
    .readdirSync(dir)
    .filter(f => f.endsWith('.json'))
    .map(f => JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8')));
  items.sort((a, b) => a.key.localeCompare(b.key));
  fs.writeFileSync(path.join(RESULTS_DIR, 'ui-quality.json'), JSON.stringify(items, null, 1));
  // MOH_UI_UPDATE_BUDGET=1 replaces entries; =max keeps the per-rule maximum of old and new
  // (build a baseline from two runs so live-content wobble cannot cause false failures).
  const mode = process.env.MOH_UI_UPDATE_BUDGET;
  if (mode === '1' || mode === 'max') {
    const old = fs.existsSync(BUDGET_FILE) ? JSON.parse(fs.readFileSync(BUDGET_FILE, 'utf8')) : {};
    const merged: Record<string, unknown> = { ...old };
    for (const it of items) {
      if (mode === 'max' && old[it.key]) {
        const m: Record<string, number> = { ...old[it.key] };
        for (const [id, n] of Object.entries(it.counts as Record<string, number>)) m[id] = Math.max(m[id] ?? 0, n);
        merged[it.key] = m;
      } else {
        merged[it.key] = it.counts;
      }
    }
    const sorted = Object.fromEntries(Object.entries(merged).sort(([a], [b]) => a.localeCompare(b)));
    fs.mkdirSync(path.dirname(BUDGET_FILE), { recursive: true });
    fs.writeFileSync(BUDGET_FILE, JSON.stringify(sorted, null, 1) + '\n');
    console.log(`[moh-ui] budget written for ${TARGET}: ${items.length} entries (${Object.keys(sorted).length} total)`);
  }
}
