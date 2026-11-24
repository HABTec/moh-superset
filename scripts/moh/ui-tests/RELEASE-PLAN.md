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

## Update 2026-11-24: results on the production replica (training)

Training was rebuilt as a verified replica of production (`tools/replica-parity.py`), then the branch was rebased on `master` and
re-tested. Gate profile, 375/768/1440 px, 60 pages measured on production, the replica before the fixes, and the replica after.

| Issue | Production today | Replica before | Replica after |
|---|---|---|---|
| RESP-BLOCKER | 16 | 16 | 0 |
| RESP-CHART-CLIP | 30 | 33 | 11 |
| RESP-INNER-CLIP | 191 | 168 | 39 |
| RESP-TAP-TARGET | 599 | 714 | 70 |
| RESP-TINY-TEXT | 53 | 42 | 6 |
| A11Y-NO-NAME (probe corrected for image alt) | 89 | 249 | 3 |
| A11Y-NO-FOCUS | 125 | 148 | 75 |
| color-contrast | 327 | 157 | 76 |
| nested-interactive | 421 | 429 | 341 |

Additions since the first plan: hidden page `<h1>`, header landmark fix (`Menu.tsx`), plot width measured beside the AI panel
(`ChartHolder.tsx`), control names and 24px hit areas (head/tail templates), focus ring, and stored-text fixes for KPI cards.

Production release steps added:
1. Code and templates: as before (deploy.sh, `--ui-check`).
2. **Stored chart text (separate approval).** On production the same substitutions are a database content change:
   run `tools/replica/45_fix_stored_text.py` adapted to production's metadata DB (dry run first, JSON backup of every changed row).
   Not part of the code deploy; without it the KPI-card contrast and tiny text counts stay at production's level.
3. Budgets: `budgets/prod.json` must be re-baselined after release (counts only ratchet down).

Not fixed, needs a decision: nested-interactive in dashboard tabs (hidden "Copy URL" button inside each tab), amber/green KPI colours,
TV page at phone width, content inside embedded third-party frames.

## Update 2026-11-24 (final): Groups A and B on the replica

Final gate run on the replica: 75/75 checks within the re-baselined budgets (budgets total 1320 -> 994 issue counts).
60 pages measured on production today, on the replica before the fixes, and on the replica after:

| Issue | Production today | Replica before | Replica after |
|---|---|---|---|
| RESP-BLOCKER | 16 | 16 | 0 |
| RESP-TABLE-CLIP | 8 | 10 | 0 |
| RESP-INNER-CLIP | 191 | 168 | 9 |
| RESP-TAP-TARGET | 599 | 714 | 41 |
| RESP-TINY-TEXT | 53 | 42 | 0 |
| A11Y-NO-FOCUS | 125 | 148 | 27 |
| color-contrast | 327 | 157 | 24 |
| region (content outside landmarks) | 111 | 111 | 0 |
| scrollable-region-focusable | 20 | 19 | 0 |
| RESP-CHART-CLIP | 30 | 33 | 11 |
| nested-interactive | 421 | 429 | 429 |

Unit tests (Menu, ChartHolder, responsiveDashboard, DashboardBuilder): the same 13 tests fail on clean `master` and with the patch;
the patch adds 5 passing tests and no failures.

Not fixed, with the reason:
- RESP-CHART-CLIP (11): the dashboards' own stored CSS gives each chart card `padding: 8px 12px 18px 12px !important`, which the chart width does not
  account for. A content change to dashboard CSS on production, not part of the code release.
- nested-interactive (429): the hidden "Copy URL" button inside every dashboard tab. Needs a product decision.
- aria-required-parent (36, welcome page): a tooltip attribute on the menu items makes the presentation fix invalid; needs a component change.
- KPI colours (amber, green) and the TV page at phone width: design decisions.
- Content inside embedded third-party frames.

Release notes for the deploy: the changed files include two Flask templates (`landing.html`, feedback `layout.html`) and the TV player
script as well as the head/tail templates and the frontend bundle. `deploy.sh` ships all of them; no database change is part of the code release.
