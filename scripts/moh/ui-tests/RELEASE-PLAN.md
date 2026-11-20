# Production release plan: responsive + accessibility foundation

Status: **proposal, not executed.** Nothing here runs without an explicit "go" from the owner.
Branch: `fix/responsive-a11y-foundation` (fast-forward from `master` a58b4041b9, which production runs).

## 1. What ships
| Area | Change |
|---|---|
| Responsive mode | On for every dashboard (opt-out: `responsive_dashboard_disabled: true` in dashboard JSON metadata). Rotate overlay only for opted-out dashboards and no longer on `/dashboard/list/`. |
| Phone layout | AI insight panel stacks under the chart; chart width accounts for plot padding; wide tables scroll inside their card. |
| Accessibility | 24 px minimum targets (dashboard tabs, chart footnote links, "Hide ASK AI"); portal bar muted text 5.4:1; portal bar wraps at 761-1100 px. |
| Tooling | UI test suite + budgets, `deploy.sh --ui-gate / --ui-check`, static CI workflow. No runtime effect. |

Size: 5 frontend files, 2 templates (`head_custom_extra.html`, `tail_js_custom_extra.html`). **No Python, migration or dependency change**, so deploy with `--frontend-only` (no pip, no DB dump/upgrade, no celery restart).

## 2. Evidence so far (be exact about what it covers)
| Claim | Label |
|---|---|
| Rotate-overlay blocker: 22 pages -> 0 on training; production baseline has 16 such pages | [Executed] (training) / [Executed] baseline (prod) |
| Tap targets 536 -> 368, inner clip 150 -> 39, names 229 -> 142 on training gate pages | [Executed] (training) |
| Budgets (training, original 3 dashboards): 0 pages over budget, no exceptions | [Executed] |
| Same effect on production's dashboards 3, 8, 10, 14 | [Reasoned]: same bundle and template as training (verified identical before the change); **not measured on production** |
| Smoke: 15/17 on training; the 2 failures (TV, feedback) pass on production and were unexplained | [Executed] / unexplained |
| Not covered: tabs outside the gate sample, widths 320/1024/1920, real phones/tablets, screen reader, RTL/Amharic, admin-only pages | NOT VERIFIED |

## 3. Preconditions (check before the window)
1. Master has not moved (`git ls-remote origin master` = a58b4041b9), or re-run the gate on training.
2. Choose a quiet window: restart takes the site down for up to a few minutes (8 gunicorn workers boot). No ETL refresh running (the script warns).
3. `MemAvailable` >= 10 GB (20 GB at last check), disk fine (536 GB).
4. A person with sudo on the server runs the deploy (the script asks for the sudo password; the agent has none).
5. Decide the merge: PR -> master (merge commit keeps history; squash is fine).

## 4. Steps
1. **Open and merge the PR** (owner). Review `git diff master...fix/responsive-a11y-foundation -- superset superset-frontend` (7 files).
2. **Dry run on the server** (no change): `/var/etls/moh-superset/scripts/moh/deploy.sh --dry-run --frontend-only`. Expect: incoming commits listed, "0 python / 0 dependency", node 22 found, no pip changes.
3. **Deploy** (as `sysadmin`, in the window): `/var/etls/moh-superset/scripts/moh/deploy.sh --frontend-only`.
   * This first release runs the *old* live script (it only gets the new one after the merge is pulled), so there is **no automatic UI gate**; the script's own health checks, bundle checks and auto-rollback still apply.
4. **Hard-refresh** (Ctrl+Shift+R): the PWA service worker may serve the old shell once.
5. **UI gate from the workstation**, against production, read-only (about 8 min):
   `scripts/moh/ui-tests/run-gate.sh --target prod --url https://mohss.habtechsolution.com`
   Pass = exit 0: no page over `budgets/prod.json`. Expected: blocker pages 16 -> 0; no budget rises. Then smoke: `npm run test:smoke`.
6. **Human check on real devices** (15 min): dashboards 3, 8, 10, 14 on a phone (portrait and landscape) and a tablet; the dashboard list; one dashboard with an AI insight panel; tab bars; the ASK AI button.
7. **Lock in:** `npm run budget:update` against production (replace per key, reviewed), commit the lower numbers.

## 5. Go / no-go and rollback
| Signal | Action |
|---|---|
| Deploy script health/bundle checks fail | Automatic rollback (existing behaviour) |
| Gate exit 1 (a budget rose) or a real-device problem | `/var/etls/moh-superset/scripts/moh/deploy.sh --rollback` (code + assets; no DB was touched, so no `--restore-db`) |
| One dashboard looks wrong but others are fine | No deploy needed: set `"responsive_dashboard_disabled": true` in that dashboard's JSON metadata (brings the rotate overlay back for that dashboard only) |
| Gate exit 3 (NOT VERIFIED) | Not a pass: re-run; do not mark the release verified |

## 6. Not part of this release (separate approvals)
* **Production chart edits:** the same Handlebars KPI cards (tiny text, grey contrast) probably exist on production. `tools/fix-handlebars-kpi.mjs` edits them (backups first, dry run, one chart, verify, rest). Needs an owner/admin account and its own go.
* **Amber KPI numbers** (`#f2a13c`, 2.1:1): a visible status-colour change; needs a design decision.
* **Automatic gate on the server:** needs Node-compatible runner, a Chromium and its system libraries (may need root), and `~/.config/moh-ui-test/prod.env` for `sysadmin`. Until then `deploy.sh --ui-gate=warn` prints that it cannot run, and step 5 is done from the workstation.
* Remaining accessibility work by issue id (about 368 small tap targets, 142 missing names on the gate pages on training), nested-interactive, landmarks; the full-profile audit of all tabs/widths.

## 7. Risks
| Risk | Likelihood / impact | Mitigation |
|---|---|---|
| Default-on changes how dashboards that were only ever used on desktop look at <= 1120 px | Medium / visible but not data-affecting; desktop (>= 1440) unchanged in the gate | Per-dashboard opt-out; real-device check; rollback |
| Tab buttons at 24 px minimum change tab-bar look | Low / cosmetic | Real-device check |
| Restart downtime | Certain, short | Quiet window; existing health check and rollback |
| Training and production differ more than assumed (training's tail template had drifted from master) | Low-medium | Step 5 measures production itself against its own baseline |
