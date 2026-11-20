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
