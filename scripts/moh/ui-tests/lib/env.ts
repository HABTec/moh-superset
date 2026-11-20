import fs from 'fs';
import os from 'os';
import path from 'path';

/** Which instance is under test. Selects the budget file and the page list. */
export const TARGET = process.env.MOH_UI_TARGET || 'prod';
export const BASE_URL = (
  process.env.MOH_UI_BASE_URL || 'https://mohss.habtechsolution.com'
).replace(/\/$/, '');

/**
 * Test credentials. Prefer MOH_UI_USER / MOH_UI_PASS. As a fallback read a
 * file outside the repository (MOH_UI_CREDS_FILE, default
 * ~/.config/moh-ui-test/<target>.env) holding either KEY=VALUE lines or the
 * three-line form "Username:" / <user> / "Password:" / <pass>.
 * Credentials are never logged.
 */
export function credentials(): { user: string; pass: string } {
  if (process.env.MOH_UI_USER && process.env.MOH_UI_PASS) {
    return { user: process.env.MOH_UI_USER, pass: process.env.MOH_UI_PASS };
  }
  const file =
    process.env.MOH_UI_CREDS_FILE ||
    path.join(os.homedir(), '.config', 'moh-ui-test', `${TARGET}.env`);
  if (!fs.existsSync(file)) {
    throw new Error(
      `No credentials: set MOH_UI_USER/MOH_UI_PASS or create ${file}`,
    );
  }
  const lines = fs
    .readFileSync(file, 'utf8')
    .split('\n')
    .map(l => l.trim())
    .filter(Boolean);
  const kv: Record<string, string> = {};
  for (const l of lines) {
    const m = l.match(/^(MOH_UI_USER|MOH_UI_PASS|MOH_TEST_USER|MOH_TEST_PASS)=(.*)$/);
    if (m) kv[m[1]] = m[2];
  }
  const user = kv.MOH_UI_USER || kv.MOH_TEST_USER;
  const pass = kv.MOH_UI_PASS || kv.MOH_TEST_PASS;
  if (user && pass) return { user, pass };
  const at = (re: RegExp) => {
    const i = lines.findIndex(l => re.test(l));
    return i >= 0 ? lines[i + 1] : undefined;
  };
  const u = at(/^username:?$/i);
  const p = at(/^password:?$/i);
  if (!u || !p) throw new Error(`Unrecognised credentials format in ${file}`);
  return { user: u, pass: p };
}

export const STATE_FILE = path.join(__dirname, '..', '.auth', `${TARGET}.json`);
export const RESULTS_DIR = path.join(
  __dirname,
  '..',
  'results',
  process.env.MOH_UI_RUN_ID || 'latest',
);
export const BUDGET_FILE = path.join(
  __dirname,
  '..',
  'budgets',
  `${TARGET}.json`,
);
