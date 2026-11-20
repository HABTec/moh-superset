#!/usr/bin/env node
/**
 * Turn a Playwright JSON report into a gate verdict.
 *   exit 0  PASS          every test within its budget
 *   exit 1  REGRESSION    at least one page is over budget ("UI regressions on ...")
 *   exit 3  NOT VERIFIED  the gate could not measure (no tests ran, login/network
 *                         errors, a page never rendered): never reported as a pass
 * Regressions win over NOT VERIFIED. Usage: gate-summary.mjs report.json [summary.txt]
 */
import fs from 'fs';

const [, , reportPath, summaryPath] = process.argv;
// eslint-disable-next-line no-control-regex
const strip = s => String(s || '').replace(/\u001b\[[0-9;]*[A-Za-z]/g, '');

export function verdict(report) {
  const regressions = [];
  const unverified = [];
  let total = 0;
  let passed = 0;
  const walk = suite => {
    for (const spec of suite.specs || []) {
      for (const t of spec.tests || []) {
        total += 1;
        if (t.status === 'expected' || t.status === 'flaky') {
          passed += 1;
        } else if (t.status === 'skipped') {
          unverified.push({ title: spec.title, why: 'skipped' });
        } else {
          const msg = strip(
            (t.results || [])
              .map(r => (r.error && r.error.message) || '')
              .filter(Boolean)
              .pop(),
          );
          if (/UI regressions on/.test(msg)) {
            regressions.push({ title: spec.title, why: msg.split('\n').slice(0, 6).join('\n   ') });
          } else {
            unverified.push({ title: spec.title, why: (msg.split('\n')[0] || 'failed without a message').slice(0, 160) });
          }
        }
      }
    }
    (suite.suites || []).forEach(walk);
  };
  (report.suites || []).forEach(walk);
  let code = 0;
  let name = 'PASS';
  if (total === 0) {
    code = 3;
    name = 'NOT VERIFIED (no tests ran: login, discovery or tooling failed)';
  } else if (regressions.length) {
    code = 1;
    name = 'REGRESSION';
  } else if (unverified.length) {
    code = 3;
    name = 'NOT VERIFIED';
  }
  return { code, name, total, passed, regressions, unverified };
}

if (process.argv[1] && process.argv[1].endsWith('gate-summary.mjs')) {
  let rep = { suites: [] };
  try {
    rep = JSON.parse(fs.readFileSync(reportPath, 'utf8'));
  } catch {
    /* missing or unreadable report: verdict() reports NOT VERIFIED */
  }
  const v = verdict(rep);
  const lines = [
    `UI gate: ${v.name}`,
    `  ${v.passed}/${v.total} page/viewport checks within budget; ${v.regressions.length} over budget; ${v.unverified.length} not verified`,
    ...v.regressions.map(r => `  OVER BUDGET  ${r.title}\n   ${r.why}`),
    ...v.unverified.slice(0, 20).map(r => `  NOT VERIFIED ${r.title}: ${r.why}`),
  ];
  const text = lines.join('\n');
  console.log(text);
  if (summaryPath) fs.writeFileSync(summaryPath, text + '\n');
  process.exit(v.code);
}
