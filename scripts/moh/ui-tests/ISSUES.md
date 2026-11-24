# Responsive and accessibility issue catalogue

Identifiers are axe-core rule ids (as is) plus the custom `RESP-*` / `A11Y-*` ids
defined in `lib/probes.ts`. Severity uses the shared scale (BLOCKER / MAJOR / MINOR /
NIT); the mapping rule is stated in the last column. Evidence is from the 2026-11-19
baseline of production (`mohss`, commit `a58b4041b9`) and the training replica.
Counts are the 375 px viewport unless noted; `pages` = pages affected out of those scanned.

| ID | What it means | Standard | Detected by | Severity | Why this severity | Prod evidence (375 px) |
|---|---|---|---|---|---|---|
| RESP-BLOCKER | Blocking "Rotate for a better view" overlay hides content | WCAG 1.3.4 Orientation | probe (text match + coverage) | BLOCKER | content unusable until dismissed; also appears on the dashboard list | dashlist, dash10, dash14 (<=768 px); all training dashboards |
| RESP-INNER-CLIP | element extends past an ancestor that hides overflow | WCAG 1.4.10 Reflow | probe | MAJOR | content cut off, no way to reach it | dash3 tabs 2-5, dash8 (chart titles/controls 30-60 px), dash10/14 tab bars 300-950 px |
| RESP-TABLE-CLIP | table wider than a clipping container, no scroll | WCAG 1.4.10 | probe | MAJOR | data unreachable | dash3 tab 2 |
| RESP-CHART-CLIP | chart canvas/svg wider than its holder | WCAG 1.4.10 | probe | MAJOR | partial charts | dash3 tab 2; training dash17 |
| RESP-OVERFLOW-X | document scrolls horizontally | WCAG 1.4.10 | probe | MAJOR | | guide @320 only |
| RESP-TAP-TARGET | interactive element < 24x24 CSS px | WCAG 2.5.8 | probe + axe `target-size` | MAJOR | mis-taps; worst on chart list (103) | 11 pages |
| RESP-TINY-TEXT | text below 11 px | WCAG 1.4.4 (practice) | probe | MINOR | | dash3 tab 2/3, dash10 |
| color-contrast | text/background contrast too low | WCAG 1.4.3 / 1.4.11 | axe | MAJOR | | 13 pages |
| nested-interactive | interactive control nested in another | WCAG 4.1.2 | axe | MAJOR | screen readers skip inner control | 9 pages (97 nodes) |
| target-size | axe form of RESP-TAP-TARGET | WCAG 2.5.8 | axe | MAJOR | | 11 pages |
| label-content-name-mismatch | accessible name differs from visible label | WCAG 2.5.3 | axe | MAJOR | voice control fails | 7 pages |
| scrollable-region-focusable | scroll area not keyboard reachable | WCAG 2.1.1 | axe | MAJOR | | 4 pages |
| aria-required-parent / aria-required-children | broken ARIA structure | WCAG 1.3.1 / 4.1.2 | axe | BLOCKER (axe "critical") | assistive tech gets wrong structure | welcome, 3 pages |
| button-name | button without accessible name | WCAG 4.1.2 | axe | BLOCKER (axe "critical") | | 1 page |
| A11Y-NO-NAME | interactive element with no name (probe cross-check) | WCAG 4.1.2 | probe | MAJOR | | dashlist 9, chartlist 30 |
| A11Y-NO-FOCUS | keyboard stop with no visible focus indicator | WCAG 2.4.7 / 2.4.11 | probe (25 Tab presses) | MAJOR | | dashlist 17/25, chartlist 19/25, ai-chat 22/24 |
| page-has-heading-one | no `h1` | WCAG 2.4.6 (practice) | axe | MINOR | | 9 pages |
| heading-order, landmark-one-main, landmark-unique, region, link-in-text-block, empty-table-header | structure/navigation hints | WCAG 1.3.1, 2.4.1 | axe | MINOR | | see results |

## Mapping rule
Axe `critical` -> BLOCKER, `serious` -> MAJOR, `moderate`/`minor` -> MINOR. Custom ids as in the table.

## Not covered by automation (needs a manual pass)
Focus order sense, focus return after dialogs, alt-text quality, screen-reader behaviour,
reduced-motion handling, zoom 200/400 % reflow beyond the 320 px width test, RTL/Amharic
overflow, and any page this read-only account cannot see (SQL Lab, alerts, settings, admin).
