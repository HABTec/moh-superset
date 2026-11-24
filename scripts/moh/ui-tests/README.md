# MoH UI tests: responsive, accessibility, smoke

Read-only Playwright suite for a running instance. It never writes data.
It is self-contained (own `package.json`) so it can run on the server or in CI without
installing the whole Superset frontend.

```bash
cd scripts/moh/ui-tests
npm ci                                   # or: npm install
npx playwright install chromium          # or use system Chrome: MOH_UI_CHANNEL=chrome
# credentials: MOH_UI_USER / MOH_UI_PASS, or a file outside the repo (see lib/env.ts)
MOH_UI_TARGET=prod MOH_UI_BASE_URL=https://mohss.habtechsolution.com npm run test:smoke
MOH_UI_TARGET=prod MOH_UI_PROFILE=gate npm run test:quality     # fast deploy check
MOH_UI_TARGET=prod npm run test:quality                         # everything
```

* `tests/smoke.spec.ts`: features still work (login, landing, dashboard list, every dashboard
  renders charts and answers its API, filter bar, TV, feedback, guide, mobile dashboard).
* `tests/ui-quality.spec.ts`: for every page (all dashboards and tabs are discovered at login)
  and viewport, counts responsive + accessibility issues and compares with
  `budgets/<target>.json`. A count may not go up; severe issues are never allowed on unbudgeted
  pages. Discovery returning 0 dashboards is an error, never a smaller test set.
* Issue ids: see `ISSUES.md`.

## Budgets (the ratchet)
After you FIX issues, run `npm run budget:update` against the instance and commit the lower
numbers; reviewers check the diff only ever goes down. Never raise a number to make a run
pass: fix the page. A budget is per target, because instances differ.

## Profiles
`MOH_UI_PROFILE=gate`: critical pages at 375/768/1440 (about 10 min). `full` (default): all
pages at 320/375/768/1024/1440/1920 (+4K for TV pages).

## Deploy guardrail (`scripts/moh/deploy.sh`)
After the restart and the existing health checks, `deploy.sh` runs `run-gate.sh` against the public URL
(about 8 minutes, read-only) and reads its exit code: 0 pass, 1 regression, 3 NOT VERIFIED.

| `--ui-gate=` | regression (exit 1) | not verified (exit 3) |
|---|---|---|
| `warn` (default) | reported, release kept | reported loudly, release kept |
| `on` | release rolled back (never after a DB migration) | reported loudly, release kept |
| `off` / `--skip-ui-gate` | not run | not run |

* The gate needs Node, test credentials (`MOH_UI_USER`/`MOH_UI_PASS`, or `~/.config/moh-ui-test/prod.env`
  for the user running the deploy) and a reachable `PUBLIC_URL`. With policy `on` a missing prerequisite
  refuses the deploy before anything changes; with `warn` it says so and skips.
* `deploy.sh --ui-check` runs only the gate on the live site: exit 0 / 1 / 3. Use it after hand edits.
* Reports are kept per release: `/var/etls/moh-superset-deploy/releases/<ts>/ui-gate/summary.txt`.
* Proof the gate fails when it should: `MOH_UI_INJECT_VIOLATION=1` adds a 2400 px element to the home page;
  the run must exit 1 and name `div#moh-injected-violation` (test-only hook, off by default).
* CI (`.github/workflows/moh-ui-tests.yml`) runs the static checks on every change (types, verdict unit
  tests, `bash -n` of deploy.sh). The live gate tests the instance that is *deployed*, not the pull request,
  so it is a manual job and is not a merge check.

## Responsive mode and the rotate overlay
Responsive mode is **on for every dashboard**. To turn it off for one dashboard, add
`"responsive_dashboard_disabled": true` to its JSON metadata (no deploy needed); only such a dashboard
gets the "rotate your device" overlay. Do not reintroduce dashboard id lists in code or templates.

## When the gate fails
1. Read `summary.txt`: it names the page, viewport, issue id and a sample selector.
2. Fix the page, not the budget. A budget may only go down (`npm run budget:update`, reviewed in the PR).
3. If the cause is outside the repository (for example text stored in a chart definition in the database),
   add a named, capped entry to `budgets/exceptions.json` with a reason and a way out, and remove it when fixed.
4. Interpreting NOT VERIFIED: the gate could not measure (login, network, a page that never rendered).
   It is not a pass; re-run with `--ui-check`.
