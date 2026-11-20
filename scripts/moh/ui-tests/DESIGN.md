# Design: generic responsive + accessibility foundation (Gate 2)

Status: proposal, awaiting approval. No application code is changed by this document.
Baseline: BASELINE-2026-11-20.md (production = origin/master a58b4041b9).

## 1. Why the earlier fixes left issues (root causes)
| # | Cause | Evidence |
|---|---|---|
| C1 | Responsive mode is an **opt-in allowlist**: `RESPONSIVE_DASHBOARD_PILOT_IDS = {3, 8}` in `responsiveDashboard.ts:32` and a second copy, regex `/dashboard/(?:3|8)/`, in `head_custom_extra.html:~848`. Every other dashboard falls back to the rotate overlay. | [Inspected] baseline: RESP-BLOCKER on dashboards 10, 14 at 375/768 |
| C2 | `isDashboardPage()` matches `/\/dashboard\//`, so `/dashboard/list/` is treated as a dashboard and gets the overlay. | [Inspected] + RESP-BLOCKER on dashlist |
| C3 | Breakpoints differ between TS (768/1120) and the template (`TABLET_BP`), and the logic lives in 1,700 lines of inline JS/CSS with polling (`MAX_POLLS`). | [Inspected] |
| C4 | The pilot itself is not clean: chart clipping remains (dashboard 8 tab 4: 11 charts at 1440). | [Executed] baseline |
| C5 | No regression check existed, so each fix was verified by eye on one or two dashboards. | [Reasoned] |

## 2. Options
| Option | What | Verdict |
|---|---|---|
| A | Add 10 and 14 to the allowlist | Rejected: repeats C1, every new dashboard breaks again |
| **B** | **Responsive mode on by default for all dashboards; per-dashboard opt-out in metadata (`responsive_dashboard_disabled: true`). One source of truth.** | **Recommended** |
| C | Delete the rotate overlay | Rejected for now: keep it only for opted-out dashboards, so nothing that relies on it is removed |
| D | Rewrite the dashboard grid | Rejected: too large, high risk for a Superset 6 fork |

## 3. Proposed change (Option B)
1. `responsiveDashboard.ts`: `isResponsiveDashboardEnabled()` returns true unless metadata disables it. Remove `PILOT_IDS`. Keep the existing opt-in metadata keys as no-ops for compatibility.
2. Template: remove the duplicated regex. The template reads **one** signal, the body class the app already sets (`moh-responsive-dashboard-mobile`), and the overlay runs only when the body carries an explicit opt-out class.
3. `isDashboardPage()`: require `/dashboard/<id-or-slug>/` and exclude `/dashboard/list/`.
4. Chart clipping (C4): make chart holders `min-width: 0; max-width: 100%` inside the responsive layout and fix the specific wide-chart cases found by RESP-CHART-CLIP; verified per page by the gate.
5. Breakpoints: export from one TS constant, inject into the template as CSS custom properties.

## 4. Accessibility pass (by issue ID, MoH-owned UI only; no edits inside Superset core components)
Order by severity and count in the baseline: RESP-TAP-TARGET (min 24x24 for portal chrome and dashboard controls), A11Y-NO-NAME (aria-label on icon buttons), A11Y-NO-FOCUS (`:focus-visible` ring token), page-has-heading-one and `region` (landmarks in the portal shell), color-contrast (theme tokens), nested-interactive (reported, fixed only where MoH owns the markup). Each fix lowers the budget in the same PR; the ratchet then locks it in.

## 5. Deploy-script guardrails (`scripts/moh/deploy.sh`)
- New step after `verify_service`: run the **gate profile** (63 tests, about 8 min) against the public URL, with the repo's `budgets/prod.json`.
- Flags: `--ui-gate=on|off|warn` (default `on`), `--skip-ui-gate` alias. On failure with `on`: release is marked failed and the existing auto-rollback runs (unless `--no-auto-rollback`).
- Missing Node/Chrome or credentials: step is reported as **NOT VERIFIED** and, in `on` mode, blocks; `--ui-gate=warn` makes it advisory.
- Budget changes are reviewed in the PR (numbers may only go down).
- CI job runs the same gate against training for every PR touching `superset-frontend/` or templates.
- Proof required before release: a deliberate violation (a 400 px wide element) must make the gate fail, then pass after removal.

## 6. Safety and verification plan
- Tests exist before any change: gate budget (63) + 17 smoke tests, both green on unchanged production.
- After the change: smoke 17/17, gate with no budget increase, plus new budgets only lower. Compare screenshots at 375/768/1440 for dashboards 3, 8, 10, 14.
- Training: its dashboards were never exercised by the pilot allowlist; default-on makes them exercised, so training verification is meaningful. Production is deployed only after Gate 4 approval.
- Rollback: unchanged deploy.sh auto-rollback; per-dashboard opt-out via metadata needs no deploy.

## 7. Risks
| Risk | Mitigation |
|---|---|
| Default-on changes layout of dashboards that were only ever viewed on desktop | Applies only at <= 1120 px; desktop (1440) budgets must not rise; opt-out metadata |
| 8-minute gate slows every deploy | Gate runs after the service is already healthy; `--ui-gate=warn` available |
| Gate needs a test account | Read-only account, creds file outside the repo, never logged |
| Tabs not in the gate sample regress | Full profile in CI nightly or on demand; marked NOT VERIFIED until run |

## 8. Decisions needed from you
1. Option B (default-on, metadata opt-out). Confirm.
2. Deploy gate default: `on` (blocks and rolls back) or `warn` (report only) for the first releases.
3. A11y scope: MoH-owned UI only (recommended) or also patch Superset core components.
