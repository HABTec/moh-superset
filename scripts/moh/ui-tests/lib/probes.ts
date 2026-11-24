import AxeBuilder from '@axe-core/playwright';
import type { Page } from '@playwright/test';

/**
 * Issue identifiers (catalogue). Axe rule ids are used as-is; custom
 * responsive checks use the RESP-* ids below.
 *
 *  RESP-OVERFLOW-X     document scrolls horizontally
 *  RESP-INNER-CLIP     element extends past an ancestor that hides overflow
 *  RESP-CHART-CLIP     chart canvas/svg wider than its holder
 *  RESP-TABLE-CLIP     table wider than a container that clips it (no scroll)
 *  RESP-BLOCKER        blocking "rotate your device" overlay in the way
 *  RESP-TAP-TARGET     interactive element smaller than 24x24 CSS px (WCAG 2.5.8)
 *  RESP-TINY-TEXT      text smaller than 11px
 *  A11Y-NO-NAME        interactive element with no accessible name
 *  A11Y-NO-FOCUS       keyboard focus stop with no visible focus indicator
 *  PERF-STUCK-LOADER   loading indicator still shown after render and a scroll sweep
 */
export type Counts = Record<string, number>;

export interface Probe {
  counts: Counts; // issue id -> count
  samples: Record<string, string[]>; // issue id -> a few selectors
  fixedCoverPct: number;
  loadTimeout: boolean; // true = page never reached a stable render
  renderMs: number;
}

const AXE_TAGS = [
  'wcag2a',
  'wcag2aa',
  'wcag21a',
  'wcag21aa',
  'wcag22aa',
  'best-practice',
];

/**
 * Wait until the page is really rendered, not just free of spinners: the React
 * app has mounted (many nodes), no loading image/spinner remains, and the DOM
 * size has been quiet for `quietMs`. A page measured before this point shows
 * the signature of a half-loaded shell and makes budgets meaningless.
 */
export async function settle(
  page: Page,
  animated = false,
): Promise<{ stable: boolean; ms: number; stuckLoaders: number }> {
  const t0 = Date.now();
  const MAX = Number(process.env.MOH_UI_SETTLE_MAX_MS || 90_000);
  const QUIET = 3000;
  const LINGER = 10_000; // loaders still shown after this long with a quiet DOM = stuck
  let last = -1;
  let quietSince = Date.now();
  let stable = false;
  let swept = false;
  let stuckLoaders = 0;
  const sweep = () =>
    page
      .evaluate(async () => {
        // scroll through the page so lazy (below-the-fold) charts start loading
        const h = () => document.body?.scrollHeight ?? 0;
        for (let y = 0; y < h(); y += 600) {
          window.scrollTo(0, y);
          await new Promise(r => setTimeout(r, 120));
        }
        window.scrollTo(0, 0);
      })
      .catch(() => undefined);
  while (Date.now() - t0 < MAX) {
    const s = await page
      .evaluate(() => ({
        nodes: document.body ? document.body.getElementsByTagName('*').length : 0,
        busy: document.querySelectorAll(
          '.loading, .ant-spin-spinning, [data-test="loading-indicator"], img[alt="Loading"]',
        ).length,
      }))
      .catch(() => ({ nodes: 0, busy: 1 })); // page reloading itself (TV player)
    // animated pages (TV slideshow) keep changing; for them only mount + no spinner counts
    const moved = !animated && (last < 0 || Math.abs(s.nodes - last) > Math.max(2, last * 0.02));
    // tiny static pages (404, chat shell) legitimately have < 60 nodes: only demand
    // a mounted app during the first 8 s, after that a quiet, spinner-free DOM counts
    const tooSmall = s.nodes < 60 && Date.now() - t0 < 8000;
    if (moved || tooSmall) quietSince = Date.now();
    last = s.nodes;
    const quietFor = Date.now() - quietSince;
    if (s.busy === 0 && quietFor >= QUIET) {
      stable = true;
      break;
    }
    // quiet DOM but a loader remains: lazy charts wait for a scroll. Sweep once,
    // then, if a loader still lingers, record it as PERF-STUCK-LOADER and go on.
    if (s.busy > 0 && quietFor >= QUIET && !swept) {
      swept = true;
      await sweep();
      quietSince = Date.now();
    } else if (s.busy > 0 && swept && quietFor >= LINGER) {
      stuckLoaders = s.busy;
      stable = true;
      break;
    }
    await page.waitForTimeout(500);
  }
  if (!swept) await sweep();
  await page.waitForTimeout(2000);
  return { stable, ms: Date.now() - t0, stuckLoaders };
}

/** probe() with one retry: pages that reload themselves can destroy the execution context. */
export async function probeStable(page: Page, animated = false): Promise<Probe> {
  try {
    return await probe(page, animated);
  } catch (e) {
    await page.waitForTimeout(3000);
    return probe(page, animated);
  }
}

export async function probe(page: Page, animated = false): Promise<Probe> {
  const counts: Counts = {};
  const samples: Record<string, string[]> = {};
  const add = (id: string, n: number, s: string[] = []) => {
    if (n > 0) {
      counts[id] = (counts[id] || 0) + n;
      samples[id] = (samples[id] || []).concat(s).slice(0, 4);
    }
  };

  const st = await settle(page, animated);
  const loadTimeout = !st.stable;
  add('PERF-STUCK-LOADER', st.stuckLoaders);

  // axe bundles its own playwright-core typings; the runtime object is the same
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const axe = await new AxeBuilder({ page: page as any }).withTags(AXE_TAGS).analyze();
  for (const v of axe.violations) {
    add(
      v.id,
      v.nodes.length,
      v.nodes.slice(0, 2).map(n => n.target.join(' ').slice(0, 90)),
    );
  }

  const m = await page.evaluate(() => {
    const de = document.documentElement;
    const vw = de.clientWidth;
    const vh = window.innerHeight;
    const vis = (e: Element) => {
      const r = e.getBoundingClientRect();
      const s = getComputedStyle(e);
      return (
        r.width > 0 &&
        r.height > 0 &&
        s.visibility !== 'hidden' &&
        s.display !== 'none'
      );
    };
    const desc = (e: Element) =>
      e.tagName.toLowerCase() +
      (e.id ? `#${e.id}` : '') +
      (e.className && typeof e.className === 'string'
        ? `.${e.className.trim().split(/\s+/)[0]}`
        : '');

    const interactive = [
      ...document.querySelectorAll(
        'a[href],button,input:not([type=hidden]),select,textarea,[role=button],[role=tab],[tabindex="0"]',
      ),
    ].filter(vis);
    const small = interactive.filter(e => {
      const r = e.getBoundingClientRect();
      return r.width < 24 || r.height < 24;
    });
    // accessible name: aria-label / labelledby / title / own text / label / alt, or the name of a descendant
    // (an <img alt>, an icon with aria-label, an svg <title>) as for links and buttons that wrap an image
    const hasName = (e: Element): boolean => {
      const h = e as HTMLInputElement;
      if (
        e.getAttribute('aria-label') ||
        e.getAttribute('aria-labelledby') ||
        e.getAttribute('title') ||
        (e.textContent || '').trim() ||
        (h.labels && h.labels.length) ||
        e.getAttribute('alt')
      )
        return true;
      return !!e.querySelector(
        'img[alt]:not([alt=""]),[aria-label]:not([aria-label=""]),svg > title,[role=img][aria-labelledby]',
      );
    };
    const noName = interactive.filter(e => !hasName(e));

    const clip: { el: string; by: string }[] = [];
    for (const e of document.querySelectorAll('body *')) {
      if (clip.length >= 40) break;
      if (!vis(e)) continue;
      const r = e.getBoundingClientRect();
      if (r.width < 8) continue;
      let a = e.parentElement;
      while (a && a !== document.body) {
        const s = getComputedStyle(a);
        if (/hidden|clip/.test(s.overflowX)) {
          const ar = a.getBoundingClientRect();
          if (ar.width > 0 && r.right > ar.right + 4 && r.left < ar.right) {
            clip.push({ el: desc(e), by: desc(a) });
          }
          break;
        }
        if (/auto|scroll/.test(s.overflowX)) break;
        a = a.parentElement;
      }
    }
    const uniqClip = [...new Map(clip.map(c => [c.el + c.by, c])).values()];

    const chartClip = [
      ...document.querySelectorAll('canvas,[data-test="chart-container"] svg'),
    ]
      .filter(vis)
      .filter(c => {
        const h = c.closest(
          '[data-test="dashboard-component-chart-holder"],.dashboard-chart,.chart-container',
        );
        return h
          ? c.getBoundingClientRect().right > h.getBoundingClientRect().right + 4
          : false;
      });

    const tableClip = [...document.querySelectorAll('table')]
      .filter(vis)
      .filter(t => {
        let a = t.parentElement;
        while (a && a !== document.body) {
          const s = getComputedStyle(a);
          if (/auto|scroll/.test(s.overflowX)) return false;
          if (/hidden|clip/.test(s.overflowX)) {
            return (
              t.getBoundingClientRect().right > a.getBoundingClientRect().right + 4
            );
          }
          a = a.parentElement;
        }
        return false;
      });

    const tiny = [...document.querySelectorAll('body *')].filter(
      e =>
        vis(e) &&
        e.children.length === 0 &&
        (e.textContent || '').trim().length > 2 &&
        parseFloat(getComputedStyle(e).fontSize) < 11,
    );

    const fixed = [...document.querySelectorAll('body *')]
      .filter(
        e => vis(e) && ['fixed', 'sticky'].includes(getComputedStyle(e).position),
      )
      .map(e => {
        const r = e.getBoundingClientRect();
        const w = Math.max(0, Math.min(r.right, vw) - Math.max(r.left, 0));
        const h = Math.max(0, Math.min(r.bottom, vh) - Math.max(r.top, 0));
        return (100 * w * h) / (vw * vh);
      })
      .filter(p => p >= 3);

    return {
      hOverflow: de.scrollWidth > vw + 1,
      overflowEls: [...document.querySelectorAll('body *')]
        .filter(
          e =>
            vis(e) &&
            e.getBoundingClientRect().right > vw + 1 &&
            getComputedStyle(e).position !== 'fixed' &&
            !e.closest('[style*="overflow"]'),
        )
        .slice(0, 3)
        .map(desc),
      small: small.length,
      smallSample: small.slice(0, 3).map(desc),
      noName: noName.length,
      noNameSample: noName.slice(0, 3).map(desc),
      innerClip: uniqClip.length,
      innerClipSample: uniqClip.slice(0, 3).map(c => `${c.el} by ${c.by}`),
      chartClip: chartClip.length,
      chartClipSample: chartClip.slice(0, 3).map(c => `${desc(c)} in ${desc(c.closest('[data-test="dashboard-component-chart-holder"],.dashboard-chart,.chart-container') as Element)}`),
      tableClip: tableClip.length,
      tableClipSample: tableClip.slice(0, 3).map(desc),
      tiny: tiny.length,
      tinySample: tiny.slice(0, 3).map(e => `${desc(e)} "${(e.textContent || '').trim().slice(0, 20)}" ${getComputedStyle(e).fontSize}`),
      blocker: /rotate for a better view/i.test(document.body.innerText),
      fixedCover: Math.min(
        100,
        +fixed.reduce((a, b) => a + b, 0).toFixed(1),
      ),
    };
  });

  add('RESP-OVERFLOW-X', m.hOverflow ? 1 : 0, m.overflowEls);
  add('RESP-INNER-CLIP', m.innerClip, m.innerClipSample);
  add('RESP-CHART-CLIP', m.chartClip, m.chartClipSample);
  add('RESP-TABLE-CLIP', m.tableClip, m.tableClipSample);
  add('RESP-BLOCKER', m.blocker ? 1 : 0);
  add('RESP-TAP-TARGET', m.small, m.smallSample);
  add('RESP-TINY-TEXT', m.tiny, m.tinySample);
  add('A11Y-NO-NAME', m.noName, m.noNameSample);

  // Keyboard probe: 25 Tab presses; count stops with no visible focus ring.
  let noFocus = 0;
  const noFocusSample: string[] = [];
  for (let i = 0; i < 25; i++) {
    await page.keyboard.press('Tab');
    const r = await page.evaluate(() => {
      const e = document.activeElement as HTMLElement | null;
      if (!e || e === document.body) return null;
      const s = getComputedStyle(e);
      const ring =
        (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) ||
        (!!s.boxShadow && s.boxShadow !== 'none');
      return {
        ring,
        d: e.tagName.toLowerCase() + (e.id ? `#${e.id}` : ''),
      };
    });
    if (r && !r.ring) {
      noFocus++;
      if (noFocusSample.length < 3) noFocusSample.push(r.d);
    }
  }
  add('A11Y-NO-FOCUS', noFocus, noFocusSample);

  // a page that never settled is remembered in its budget as _unstable
  if (loadTimeout) counts._unstable = 1;
  return { counts, samples, fixedCoverPct: m.fixedCover, loadTimeout, renderMs: st.ms };
}
