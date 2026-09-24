# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.
"""
MoH brand assets served by Flask.

The frontend webpack build (`npm run build`) cleans `superset/static/assets/`
on every run, which would delete any manually-placed logo PNG we put there.
This blueprint serves the brand assets from a webpack-safe directory
(`superset/templates/superset/`) under a stable URL that survives rebuilds:

    GET /moh-static/<filename>

Allowlist enforced — only specifically listed files are returned, so this
blueprint cannot be used as a generic file read primitive against the
templates folder.

Registered in `superset/moh_branding.py` via the BLUEPRINTS config list.
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
)
from flask_login import current_user

moh_assets_bp = Blueprint(
    "moh_assets",
    __name__,
    url_prefix="/moh-static",
)

# Add new files here to expose them. The directory below is git-tracked and
# never touched by webpack, so files placed here are durable across builds
# and deployments.
_BRAND_ASSET_DIR = os.path.join(
    os.path.dirname(__file__), "templates", "superset"
)
_ALLOWED_FILES: set[str] = {
    "logomohnewww.png",
    "moh_icon.png",
    "arrow.png",
    "blank-style.json",
    "moh_tv_player.js",
}

# Screenshots embedded in the user guide (superset/templates/superset/guide_images/).
_ALLOWED_FILES.update(
    f"guide_images/{name}"
    for name in (
        "01-login-page.png",
        "02-landing-page.png",
        "03-summary-dashboard.png",
        "04-data-quality-dashboard.png",
        "05-filters-panel.png",
        "06-monthly-dashboard.png",
        "07-line-chart-tooltip.png",
        "08-multi-source-dashboard.png",
        "09-triangulation-chart.png",
        "10-health-intelligence-dashboard.png",
        "11-ai-assistant-chat.png",
        "12-ai-assistant-anomaly.png",
        "13-ai-assistant-feedback-alerts.png",
    )
)

# Branded static pages (the user guide) served at a clean public URL.
moh_guide_bp = Blueprint("moh_guide", __name__)

# Yengwe palette.html — cool module accents; red/amber/green stay for status.
_TV_MODULE_ACCENTS: tuple[tuple[str, str], ...] = (
    ("ncd", "#1F7A6C"),
    ("maternal", "#8B3A76"),
    ("neonatal", "#8B3A76"),
    ("equity", "#3B4E9B"),
    ("malaria", "#2F6F8F"),
    ("phem", "#5B3E8C"),
    ("phc", "#4A5A68"),
    ("hiv", "#2F6F8F"),
    ("tb", "#2F6F8F"),
    ("family planning", "#0374B8"),
    ("familly planning", "#0374B8"),
    ("health work", "#3B4E9B"),
    ("financing", "#4A5A68"),
    ("supply", "#2F6F8F"),
    ("digital", "#1F7A6C"),
    ("infrastructure", "#4A5A68"),
    ("blood", "#8B3A76"),
)


def tv_slide_accent(label: str, path: list[str] | None = None) -> str:
    """Pick the Yengwe module hue from the slide title or tab path."""
    haystack = f"{label} {' '.join(path or [])}".lower()
    for needle, color in _TV_MODULE_ACCENTS:
        if needle in haystack:
            return color
    return "#0374B8"


# Module → source label when a slide does not set ``source`` itself.
_TV_MODULE_SOURCES: tuple[tuple[str, str], ...] = (
    ("health equity", "EDHS · Survey"),
    ("health work", "NHWA"),
    ("financing", "NHA"),
    ("supply", "eLMIS"),
    ("logistics", "eLMIS"),
    ("blood", "DHIS2 · Blood"),
    ("phem", "DHIS2 · Surveillance"),
    ("phc", "DHIS2 · PHC"),
    ("digital", "HIS"),
    ("infrastructure", "HFR"),
    ("data quality", "DHIS2 · Quality"),
    ("multi source", "Multiple sources"),
    ("triangulation", "Multiple sources"),
)


def tv_slide_source(
    label: str,
    path: list[str] | None = None,
    explicit: str | None = None,
) -> str:
    """Pick the context-strip source for a slide.

    An explicit ``source`` on the slide config wins. Otherwise the tab path
    is matched to the module list above. Service-delivery slides fall back
    to DHIS2 routine.
    """
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    haystack = f"{label} {' '.join(path or [])}".lower()
    for needle, source in _TV_MODULE_SOURCES:
        if needle in haystack:
            return source
    return "DHIS2 · Routine"


def tv_embed_url(dashboard: str, preset: str) -> str:
    """Same-window dashboard URL for the TV shell (no iframe, one login)."""
    parts = urlsplit(dashboard or "/superset/dashboard/8/")
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.setdefault("standalone", "2")
    query["expand_filters"] = "false"
    query["moh_tv"] = preset
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


_TV_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MoH Dashboard TV</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">
<style>
  :root {
    --tv-letterbox: #05080B;
    --tv-ink: #14181D;
    --tv-ink-2: #52606D;
    --tv-ink-3: #626B77;
    --tv-card: #FFFFFF;
    --tv-rule: #DCE4EC;
    --tv-ok: #1E7A4C;
    --tv-ok-bg: #E6F4EC;
    --tv-warn: #8F5D00;
    --tv-warn-bg: #FBF0DE;
    --tv-mod: #0374B8;
    --tv-font: Inter, -apple-system, "Segoe UI", Roboto, sans-serif;
    --tv-mast-h: 72px;
    --tv-strip-h: 74px;
    --tv-head-h: 68px;
  }
  html, body { margin: 0; height: 100%; background: var(--tv-letterbox); overflow: hidden; }
  body.idle { cursor: none; }
  #panel { position: fixed; inset: 0; background: var(--tv-letterbox); overflow: hidden; }
  #screen {
    position: absolute; left: 0; top: 0; width: 1920px; height: 1080px;
    transform-origin: 0 0; overflow: hidden;
    background: #EEF2F6; color: var(--tv-ink); font-family: var(--tv-font);
    display: flex; flex-direction: column;
  }
  #mast {
    flex: none; height: var(--tv-mast-h); background: var(--tv-ink);
    display: flex; align-items: center; gap: 20px; padding: 0 40px; color: #fff;
  }
  #mast img { width: 52px; height: 52px; object-fit: contain; flex: none; }
  #mast .w1 { font-size: 27px; font-weight: 700; letter-spacing: -.01em; }
  #mast .w2 { font-size: 19px; font-weight: 500; color: rgba(255,255,255,.72); }
  #mast .cal { margin-left: auto; text-align: right; }
  #mast .c1 { font-size: 23px; font-weight: 600; }
  #mast .c2 { font-size: 17px; color: rgba(255,255,255,.62); }
  #strip {
    flex: none; height: var(--tv-strip-h); background: var(--tv-card);
    border-bottom: 2px solid var(--tv-rule);
    display: flex; align-items: center; gap: 20px; padding: 0 40px;
  }
  .strip-item { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
  .strip-k {
    font-size: 18px; font-weight: 600; letter-spacing: .1em;
    text-transform: uppercase; color: var(--tv-ink-3);
  }
  .strip-v { font-size: 24px; font-weight: 600; white-space: nowrap; }
  .strip-sep { width: 1px; align-self: stretch; background: var(--tv-rule); margin: 18px 0; }
  .fresh {
    margin-left: auto; display: inline-flex; align-items: center; gap: 10px;
    background: var(--tv-ok-bg); color: var(--tv-ok);
    border-radius: 8px; padding: 8px 16px; font-size: 24px; font-weight: 600;
  }
  .fresh.stale { background: var(--tv-warn-bg); color: var(--tv-warn); }
  .fresh .dot { width: 14px; height: 14px; border-radius: 50%; background: currentColor; }
  #head {
    flex: none; height: var(--tv-head-h);
    display: flex; align-items: center; gap: 18px; padding: 0 40px;
    border-top: 6px solid var(--tv-mod);
    background: linear-gradient(to bottom, color-mix(in srgb, var(--tv-mod) 7%, transparent), transparent);
  }
  #glyph {
    min-width: 54px; height: 54px; padding: 0 12px; border-radius: 11px;
    background: var(--tv-mod); color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-size: 22px; font-weight: 700;
  }
  #slideTitle { font-size: 44px; font-weight: 700; letter-spacing: -.015em; line-height: 1.1; }
  #stage { flex: 1 1 auto; min-height: 0; position: relative; overflow: hidden; background: #fff; }
  #tv { position: absolute; inset: 0; width: 100%; height: 100%; border: 0; background: #fff; }
  #label {
    position: absolute; left: 16px; bottom: 10px; z-index: 10;
    font: 600 22px/1.2 var(--tv-font); color: #fff;
    background: rgba(0,0,0,.45); padding: 6px 12px; border-radius: 8px;
    pointer-events: none;
  }
  #empty {
    position: fixed; inset: 0; display: flex; align-items: center;
    justify-content: center; color: #ccc;
    font: 400 22px/1.5 var(--tv-font); text-align: center; padding: 24px;
  }
  #controls {
    position: fixed; bottom: 18px; left: 50%; transform: translateX(-50%);
    z-index: 20; display: flex; gap: 10px;
  }
  #controls button {
    font: 600 15px/1 var(--tv-font); color: #fff;
    background: rgba(0,0,0,.5); border: 0; cursor: pointer;
    padding: 9px 18px; border-radius: 8px; opacity: .38;
    transition: opacity .25s;
  }
  #controls button:hover { opacity: 1; }
</style>
</head>
<body>
  <div id="panel">
    <div id="screen">
      <div id="mast">
        <img id="mastLogo" alt="Ministry of Health" src="/moh-static/logomohnewww.png">
        <div>
          <div class="w1" id="mastTitle">Ministry of Health</div>
          <div class="w2" id="mastWord">Service Delivery</div>
        </div>
        <div class="cal">
          <div class="c1" id="mastPeriod"></div>
        </div>
      </div>
      <div id="strip">
        <div class="strip-item">
          <div class="strip-k">Geography</div>
          <div class="strip-v" id="stripGeo">National · Ethiopia</div>
        </div>
        <div class="strip-sep"></div>
        <div class="strip-item">
          <div class="strip-k">Period</div>
          <div class="strip-v" id="stripPeriod">2018 EFY</div>
        </div>
        <div class="strip-sep"></div>
        <div class="strip-item">
          <div class="strip-k">Source</div>
          <div class="strip-v" id="stripSource">DHIS2 · Routine</div>
        </div>
        <div class="fresh" id="freshChip"><span class="dot"></span><span id="freshText">Data as of …</span></div>
      </div>
      <div id="head">
        <div id="glyph">TV</div>
        <div id="slideTitle"></div>
      </div>
      <div id="stage">
        <iframe id="tv" referrerpolicy="same-origin"></iframe>
        <div id="label"></div>
      </div>
    </div>
  </div>
  <div id="controls">
    <button id="prevBtn" type="button">◀ Prev</button>
    <button id="fsBtn"   type="button">⛶ Fullscreen</button>
    <button id="nextBtn" type="button">Next ▶</button>
  </div>
  <script>
    const CFG = __CONFIG__;
    CFG.canvas = CFG.canvas || { width: 1920, height: 1080 };
    CFG.skipEmptyRatio = CFG.skipEmptyRatio || 0.8;
    CFG.readyTimeoutMs = CFG.readyTimeoutMs || 25000;
    CFG.emptyMarkers = CFG.emptyMarkers || [];
    const frame = document.getElementById('tv');
    const screenEl = document.getElementById('screen');
    const label = document.getElementById('label');
    const controls = document.getElementById('controls');
    const prevBtn = document.getElementById('prevBtn');
    const fsBtn = document.getElementById('fsBtn');
    const nextBtn = document.getElementById('nextBtn');
    CFG.chrome = CFG.chrome || {};

    (function idleCursor() {
      let t = 0;
      const bump = () => {
        document.body.classList.remove('idle');
        clearTimeout(t);
        t = setTimeout(() => document.body.classList.add('idle'), 3000);
      };
      ['mousemove', 'keydown', 'pointerdown'].forEach(ev =>
        document.addEventListener(ev, bump, { passive: true }));
      bump();
    })();

    function placeScreen() {
      if (!screenEl) return;
      const k = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
      screenEl.style.transform =
        'translate(' + ((window.innerWidth - 1920 * k) / 2) + 'px,'
        + ((window.innerHeight - 1080 * k) / 2) + 'px) scale(' + k + ')';
    }
    placeScreen();
    window.addEventListener('resize', placeScreen);

    // Hide the browser chrome. Browsers require a user gesture before
    // allowing fullscreen, so we (1) try silently on load, (2) offer a
    // button that floats ABOVE the iframe, and (3) forward taps/keys that
    // land inside the iframe document back to this page.
    function goFullscreen() {
      const el = document.documentElement;
      const fn = el.requestFullscreen || el.webkitRequestFullscreen
        || el.mozRequestFullScreen || el.msRequestFullscreen;
      if (fn && !document.fullscreenElement && !document.webkitFullscreenElement) {
        try { fn.call(el); } catch (e) { /* needs gesture */ }
      }
    }
    function toggleFullscreen() {
      if (document.fullscreenElement || document.webkitFullscreenElement) {
        (document.exitFullscreen || document.webkitExitFullscreen || function(){}).call(document);
      } else {
        goFullscreen();
      }
    }
    function syncControls() {
      const full =
        !!(document.fullscreenElement || document.webkitFullscreenElement);
      fsBtn.textContent = full ? '⛶ Exit' : '⛶ Fullscreen';
    }
    goFullscreen();
    document.addEventListener('fullscreenchange', syncControls);
    document.addEventListener('webkitfullscreenchange', syncControls);

    // Taps inside the iframe never reach this document (the dashboard fills
    // it completely), so listen there too — same-origin makes that possible.
      // Attach to the iframe document's grid element: whenever it resizes
      // (charts load late, data arrives), re-fit immediately instead of
      // waiting for the next scheduled pass.
      let resizeObs = null;
      let resizeObsTarget = null;
      function wireResizeObserver(doc) {
        const target =
          doc.querySelector('[data-test="grid-content"]')
          || doc.querySelector('.grid-content')
          || doc.querySelector('.dashboard-grid');
        if (!target || target === resizeObsTarget) return;
        if (resizeObs) resizeObs.disconnect();
        resizeObsTarget = target;
        resizeObs = new ResizeObserver(() => fit());
        resizeObs.observe(target);
      }

      function wireIframeGestures() {
        let doc = null;
        try { doc = frame.contentDocument; } catch (e) { return; }
        if (!doc || doc.__mohTvWired) return;
        doc.__mohTvWired = true;
        doc.addEventListener('click', goFullscreen);
        doc.addEventListener('touchstart', goFullscreen);
        doc.addEventListener('keydown', goFullscreen);
      }

    if (!CFG.url || !CFG.slides.length) {
      document.body.innerHTML =
        '<div id="empty">No TV slides configured.<br>'
        + 'Set MOH_TV_SLIDES / MOH_TV_GROUPS in superset_config.py.</div>';
    } else {
      let i = -1;
      let fitTimers = [];
      let token = 0;        // guards against overlapping slide switches
      let pending = -1;     // slide to activate after the iframe loads
      let clipped = false;  // slide taller than the stage — clip, do not scale
      let skipStreak = 0;   // consecutive skipped slides, so an all-empty loop still shows something
      let watchdog = null;
      const warned = {};

      const CANVAS_W = CFG.canvas.width;
      const CANVAS_H = CFG.canvas.height;
      const THEME_KEY = 'superset-dev-theme-override';

      const sleep = ms => new Promise(r => setTimeout(r, ms));

      // Give the wall its own theme (larger type) without touching the
      // database or the desktop theme: Superset's theme controller reads this
      // local-storage key when the dashboard starts and merges it over the
      // default theme. It is removed when this page is left, so a normal tab
      // in the same browser profile is not affected.
      if (CFG.theme) {
        try {
          localStorage.setItem(THEME_KEY, JSON.stringify(CFG.theme));
          window.addEventListener('pagehide', () => {
            try { localStorage.removeItem(THEME_KEY); } catch (e) { /* ignore */ }
          });
        } catch (e) { /* storage blocked: the desktop theme is used */ }
      }

      function resetFrame() {
        frame.style.width = '100%';
        frame.style.height = '100%';
        frame.style.transform = '';
      }

      function setAccent(color) {
        document.documentElement.style.setProperty('--tv-mod', color || '#0374B8');
      }

      function glyphText(title) {
        const words = String(title || '').trim().split(/\s+/).filter(Boolean);
        if (!words.length) return 'TV';
        if (words.length === 1) return words[0].slice(0, 3).toUpperCase();
        return words.slice(0, 2).map(w => w[0]).join('').toUpperCase();
      }

      function paintChrome(n) {
        const slide = CFG.slides[n === undefined ? i : n] || {};
        const chrome = CFG.chrome;
        const title = slide.label || '';
        setAccent(slide.accent || '#0374B8');
        const $ = id => document.getElementById(id);
        if ($('mastTitle')) $('mastTitle').textContent = chrome.title || 'Ministry of Health';
        if ($('mastWord')) $('mastWord').textContent = chrome.wordmark || '';
        if ($('mastPeriod')) $('mastPeriod').textContent = chrome.period || '';
        if ($('mastLogo') && chrome.logoUrl) $('mastLogo').src = chrome.logoUrl;
        if ($('stripGeo')) $('stripGeo').textContent = chrome.geography || '';
        if ($('stripPeriod')) $('stripPeriod').textContent = chrome.period || '';
        if ($('stripSource')) $('stripSource').textContent = chrome.source || '';
        if ($('slideTitle')) $('slideTitle').textContent = title;
        if ($('glyph')) $('glyph').textContent = glyphText(title);
        if (label) {
          label.textContent = clipped
            ? title + ' · too tall — clipped, not scaled'
            : '';
          label.style.display = clipped ? 'block' : 'none';
        }
        if (clipped && title && !warned[title]) {
          warned[title] = true;
          console.warn('TV: "' + title + '" is taller than the 1920×1080 stage. '
            + 'Split or trim the dashboard tab. Type is not scaled.');
        }
      }

      function formatFreshness(period) {
        if (!period || period.fiscalYear == null) return null;
        const fy = String(period.fiscalYear);
        const year = /^\d{4}$/.test(fy) ? fy + ' EFY' : fy;
        const extra = period.monthName || (period.quarter != null ? ('Q' + period.quarter) : '');
        return extra ? year + ' · ' + extra : year;
      }

      (function loadFreshness() {
        const url = CFG.chrome.freshnessUrl;
        const chip = document.getElementById('freshChip');
        const text = document.getElementById('freshText');
        if (!url || !chip || !text) return;
        fetch(url, { credentials: 'same-origin' })
          .then(r => r.ok ? r.json() : Promise.reject())
          .then(data => {
            const asOf = formatFreshness(
              (data.sources && data.sources.routine && data.sources.routine.monthly)
              || (data.sources && data.sources.routine && data.sources.routine.quarterly)
            );
            if (asOf) {
              text.textContent = 'Data as of ' + asOf;
              chip.classList.remove('stale');
            } else {
              text.textContent = 'Data as of Not available';
              chip.classList.add('stale');
            }
          })
          .catch(() => {
            text.textContent = 'Data as of Not available';
            chip.classList.add('stale');
          });
      })();

      function updateLabel(n) {
        paintChrome(n);
      }

      function safeDoc() {
        try { return frame.contentDocument; } catch (e) { return null; }
      }

      function bust(u) {
        return u + (u.indexOf('?') > -1 ? '&' : '?')
          + 'expand_filters=false&_tv=' + Date.now();
      }

      // One stylesheet, injected once: unlock natural height, lift Superset's
      // internal width caps (viewport-minus-filter-bar), hide chrome and all
      // dashboard tab bars.
      function unlockScroll(doc) {
        if (doc.getElementById('moh-tv-unlock')) return;
        const st = doc.createElement('style');
        st.id = 'moh-tv-unlock';
        st.textContent =
          'html,body{height:auto!important;overflow:hidden!important;margin:0!important;' +
          'font-family:Inter,-apple-system,"Segoe UI",Roboto,sans-serif!important;}' +
          '#app,.ant-layout,.ant-layout-content,.ant-layout-content>div,' +
          '.dashboard,.dashboard-content,.grid-content,[data-test="grid-content"]' +
          '{height:auto!important;max-height:none!important;overflow:visible!important;margin:0!important;padding:0!important;}' +
          '.dashboard{padding-top:0!important;margin-top:0!important;}' +
          'body{overflow:hidden!important;}' +
          '#main-menu, header.top, .navbar, .ant-layout-header, .dashboard-header-container,' +
          '[data-test="dashboard-header-wrapper"], .dashboard-header-container .header-with-actions,' +
          '[data-test="dashboard-filters-panel"], .dashboard-filters-panel,' +
          '.moh-ai-overlay,#mohAiOverlay,.moh-ai-toggle,#mohAiToggle,#mohAiPanel,' +
          '[class*="HoverMenu"],.hover-menu,[data-test="dashboard-component-chart-holder"] .header-controls' +
          '{display:none!important;}' +
          '.dashboard,.dashboard-content,[data-test="dashboard-content"],' +
          '[class*="dashboard-builder"],.grid-content,[data-test="grid-content"],' +
          '.dashboard-grid{max-width:none!important;width:auto!important;}' +
          '.ant-tabs-nav,[data-test="dashboard-component-tabs"] .ant-tabs-nav' +
          '{display:none!important;}';
        (doc.head || doc.documentElement).appendChild(st);
      }

      function contentHeight(doc) {
        const grid = doc.querySelector('[data-test="grid-content"]')
          || doc.querySelector('.grid-content')
          || doc.querySelector('.dashboard-grid');
        if (grid && grid.scrollHeight > 40) return grid.scrollHeight;
        return (doc.body && doc.body.scrollHeight) || window.innerHeight;
      }

      // Inline styles survive antd re-renders that would outrun the injected
      // stylesheet; runs again on every fit pass.
      function hideTabBars(doc) {
        doc.querySelectorAll(
          '.ant-tabs-nav, [data-test="dashboard-component-tabs"] .ant-tabs-nav'
        ).forEach(el => { el.style.display = 'none'; });
      }

      // The 1920×1080 screen (mast + strip + slide) is letterboxed to the
      // panel. Dashboard pixels stay 1:1 inside the stage. A tab taller than
      // the stage is clipped and flagged — never scaled, so the 22 px floor
      // cannot be lost (Yengwe TV-01 / TV-02).
      function fit() {
        const doc = safeDoc();
        if (!doc || !doc.body) return;
        unlockScroll(doc);
        hideTabBars(doc);
        wireIframeGestures();
        wireResizeObserver(doc);
        resetFrame();
        const stage = document.getElementById('stage');
        const stageH = (stage && stage.clientHeight) || CANVAS_H;
        clipped = contentHeight(doc) > stageH + 8;
        updateLabel();
      }

      function scheduleFit() {
        fitTimers.forEach(clearTimeout);
        // Only a short bootstrap — after the ResizeObserver is wired it
        // catches every subsequent size change instantly and indefinitely.
        fitTimers = [800, 2000, 5000].map(t => setTimeout(fit, t));
      }

      const isVisible = el =>
        !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);

      function findTab(doc, title) {
        let fallback = null;
        for (const t of doc.querySelectorAll('.ant-tabs-tab')) {
          const btn = t.querySelector('.ant-tabs-tab-btn');
          if (((btn || t).textContent || '').trim() === title) {
            if (isVisible(t)) return t;
            fallback = fallback || t;
          }
        }
        return fallback;
      }

      async function clickPath(path, my) {
        for (const title of path) {
          if (my !== token) return false;
          let el = null;
          // The SPA hydrates asynchronously after load — retry briefly.
          for (let a = 0; a < 10 && !(el = findTab(safeDoc(), title)); a++) {
            await sleep(400);
            if (my !== token) return false;
          }
          if (!el) throw new Error('tab not found: ' + title);
          el.click();
          await sleep(450);
          if (my !== token) return false;
        }
        await sleep(1000);   // let charts mount before measuring
        return true;
      }

      // What the visible charts are doing, read from the dashboard DOM.
      // "Empty" is Superset's own no-results message; a chart that failed
      // shows an error alert instead. Selectors and the empty wording come
      // from the Superset build in this repo (see MOH_TV_EMPTY_MARKERS).
      function slideState(doc) {
        const st = { total: 0, loading: 0, empty: 0, error: 0 };
        if (!doc) return st;
        doc.querySelectorAll('[data-test="dashboard-component-chart-holder"]')
          .forEach(holder => {
            if (!isVisible(holder)) return;
            st.total++;
            if (holder.querySelector('[data-test="loading-indicator"]')) {
              st.loading++;
            } else if (holder.querySelector('.ant-alert-error,[data-test="error-message"]')) {
              st.error++;
            } else {
              const text = holder.textContent || '';
              if (CFG.emptyMarkers.some(m => text.indexOf(m) !== -1)) st.empty++;
            }
          });
        return st;
      }

      // Wait until the slide's charts have stopped loading, then decide
      // whether it has anything to show. The dwell timer starts only now, so a
      // slow slide is not charged for its loading time, and a slide with
      // nothing to show is skipped instead of holding the room for a full slot.
      async function settle(n, my) {
        const t0 = Date.now();
        let calm = 0;
        while (my === token && Date.now() - t0 < CFG.readyTimeoutMs) {
          await sleep(500);
          const st = slideState(safeDoc());
          const quiet = st.total > 0 ? st.loading === 0 : Date.now() - t0 >= 4000;
          calm = quiet ? calm + 1 : 0;
          if (calm >= 3) break;
        }
        if (my !== token) return;
        fit();

        const doc = safeDoc();
        const st = slideState(doc);
        const blank = st.total === 0 && contentHeight(doc) < 120;
        const unusable = st.total > 0 &&
          (st.empty + st.error) / st.total >= CFG.skipEmptyRatio;
        if ((blank || unusable) && CFG.slides.length > 1
            && skipStreak < CFG.slides.length - 1) {
          skipStreak++;
          console.warn('TV: skipping "' + CFG.slides[n].label + '" — '
            + (blank ? 'nothing rendered'
              : (st.empty + st.error) + ' of ' + st.total + ' cards empty or failed'));
          next();
          return;
        }
        skipStreak = 0;
        startTimer();
      }

      async function run(n) {
        const my = ++token;
        clipped = false;
        updateLabel(n);
        resetFrame();
        stopTimer();

        const doc = safeDoc();
        const ready = doc &&
          doc.querySelector('[data-test="grid-content"],.grid-content,.dashboard-grid');
        if (!ready) { pending = n; frame.src = bust(CFG.url); return; }

        try {
          if (await clickPath(CFG.slides[n].path, my) && my === token) {
            scheduleFit();
            await settle(n, my);
          }
        } catch (e) {
          if (my !== token) return;
          pending = n;                    // dashboard drifted — hard resync
          frame.src = bust(CFG.url);
        }
      }

      function iframeIsLogin(doc) {
        if (!doc) return false;
        try {
          if ((doc.location.pathname || '').indexOf('/login') !== -1) return true;
        } catch (e) { /* ignore */ }
        return !!(
          doc.querySelector('input[name="username"], input[name="password"], form[action*="login"]')
        );
      }
      function bounceToParentLogin() {
        const next = encodeURIComponent(location.pathname + location.search);
        window.location.replace('/login/?next=' + next);
      }

      frame.addEventListener('load', () => {
        if (iframeIsLogin(safeDoc())) {
          bounceToParentLogin();
          return;
        }
        scheduleFit();
        if (pending >= 0) {
          const n = pending;
          pending = -1;
          setTimeout(() => run(n), 1200);   // give the SPA time to hydrate
        }
      });
      window.addEventListener('resize', fit);

      // The dwell timer starts when a slide is ready (see settle), including
      // after a manual ◀/▶, so every slide gets its full interval on screen.
      // The watchdog starts it anyway if a slide never reports ready, so the
      // rotation cannot stall on a broken slide.
      let slideTimer = null;
      function startTimer() {
        stopTimer();
        clearTimeout(watchdog);
        if (CFG.slides.length > 1) slideTimer = setInterval(next, CFG.intervalMs);
      }
      function stopTimer() { if (slideTimer) { clearInterval(slideTimer); slideTimer = null; } }
      function go() {
        stopTimer();
        clearTimeout(watchdog);
        watchdog = setTimeout(() => { if (!slideTimer) startTimer(); },
          CFG.readyTimeoutMs + 20000);
        run(i);
      }
      function next() { i = (i + 1) % CFG.slides.length; go(); }
      function prev() { i = (i - 1 + CFG.slides.length) % CFG.slides.length; go(); }

      document.addEventListener('keydown', e => {
        if (e.key === 'ArrowRight') next();
        else if (e.key === 'ArrowLeft') prev();
        else goFullscreen();
      });
      controls.addEventListener('click', e => {
        e.stopPropagation();
        if (e.target === nextBtn) next();
        else if (e.target === prevBtn) prev();
        else if (e.target === fsBtn) toggleFullscreen();
      });

      next();
      // Safety net: even without per-slide reloads, freshen everything now
      // and then (0 disables).
      if (CFG.reloadMinutes > 0) {
        setInterval(() => location.reload(), CFG.reloadMinutes * 60000);
      }
    }
  </script>
</body>
</html>
"""


def default_tv_theme(tokens: dict[str, Any] | None = None) -> dict[str, Any]:
    """Theme override for the wall TV, derived from ``MOH_TV_TYPE_SCALE_TOKENS``.

    Type sizes are chosen for a 55-inch 1080p panel viewed from 3 m, where one
    CSS pixel subtends about 0.727 arcminutes and readable text needs about 16,
    so nothing readable may be smaller than 22 px. Chart text is a separate
    setting because ECharts draws on a canvas and ignores the component font
    size. ``hideOverlap`` makes crowded labels thin out instead of shrinking.
    """
    tokens = tokens or {}
    floor = int(tokens.get("tv_size_floor", 22))
    chart = int(tokens.get("tv_size_chart", 24))
    title = int(tokens.get("tv_size_title", 30))
    axis_label = {"fontSize": chart, "hideOverlap": True}
    return {
        "token": {
            "fontSize": floor,
            "fontSizeHeading3": title,
            "fontFamily": 'Inter, -apple-system, "Segoe UI", Roboto, sans-serif',
            "colorPrimary": "#0374B8",
            "colorTextTertiary": "#626B77",
            "colorWarning": "#8F5D00",
        },
        "echartsOptionsOverrides": {
            "textStyle": {"fontSize": chart},
            "legend": {"textStyle": {"fontSize": chart}},
            "xAxis": {"axisLabel": axis_label},
            "yAxis": {"axisLabel": axis_label},
        },
        "echartsOptionsOverridesByChartType": {
            "echarts_timeseries": {
                "xAxis": {"axisLabel": {**axis_label, "rotate": 0}},
            },
        },
    }


def _tv_options(wordmark: str | None = None) -> dict[str, Any]:
    """Shell behaviour settings, read from config with safe defaults."""
    config = current_app.config
    theme = config.get("MOH_TV_THEME")
    if theme is None:
        theme = default_tv_theme(config.get("MOH_TV_TYPE_SCALE_TOKENS"))
    return {
        "theme": theme or None,
        "canvas": {
            "width": int(config.get("MOH_TV_CANVAS_WIDTH", 1920) or 1920),
            "height": int(config.get("MOH_TV_CANVAS_HEIGHT", 1080) or 1080),
        },
        "skipEmptyRatio": float(config.get("MOH_TV_SKIP_EMPTY_RATIO", 0.8)),
        "readyTimeoutMs": int(config.get("MOH_TV_READY_TIMEOUT_SECONDS", 25)) * 1000,
        "emptyMarkers": list(
            config.get(
                "MOH_TV_EMPTY_MARKERS",
                ["No results were returned for this query", "No data"],
            )
        ),
        "chrome": {
            "title": str(config.get("MOH_TV_MASTHEAD_TITLE") or "Ministry of Health"),
            "wordmark": str(
                config.get("MOH_TV_WORDMARK") or wordmark or "Service Delivery"
            ),
            "geography": str(
                config.get("MOH_TV_GEOGRAPHY") or "National · Ethiopia"
            ),
            "period": str(config.get("MOH_TV_PERIOD") or ""),
            "source": str(config.get("MOH_TV_SOURCE") or "DHIS2 · Routine"),
            "logoUrl": str(
                config.get("MOH_TV_LOGO_URL") or "/moh-static/logomohnewww.png"
            ),
            "freshnessUrl": "/api/v1/moh/dhis2/data-freshness",
        },
    }


def _tv_slide_payload(slide: dict) -> dict[str, Any]:
    path = [str(part) for part in slide.get("path", [])]
    label = str(slide.get("label", "") or "")
    explicit = slide.get("source")
    return {
        "path": path,
        "label": label,
        "accent": tv_slide_accent(label, path),
        "source": tv_slide_source(
            label,
            path,
            str(explicit) if explicit is not None else None,
        ),
    }


def _tv_page_payload(
    slides_cfg: dict,
    interval_seconds: int,
    reload_minutes: int,
    options: dict[str, Any] | None = None,
) -> dict:
    """Build the JSON payload consumed by the TV page script.

    slides_cfg shape:
        {"dashboard": "/superset/dashboard/8/?standalone=2",
         "slides": [{"path": ["Services Delivery", "NCD"], "label": "NCD"}, ...]}
    Slides reference TABS BY TITLE PATH instead of URL, so switching happens
    by clicking tabs inside one live iframe — no page reload per slide.

    ``options`` carries the shell settings from ``_tv_options()``; without it
    the page falls back to the defaults built into its script.
    """
    return {
        "url": str(slides_cfg.get("dashboard", "") or ""),
        "slides": [
            _tv_slide_payload(s)
            for s in slides_cfg.get("slides", [])
            if s.get("path")
        ],
        "intervalMs": int(interval_seconds) * 1000,
        "reloadMinutes": int(reload_minutes),
        **(options or {}),
    }


def _render_tv_page(payload: dict) -> str:
    js = json.dumps(payload).replace("</", "<\\/")
    return _TV_PAGE.replace("__CONFIG__", js)


def _tv_response(
    cfg_key: str,
    interval_key: str,
    default_interval: int = 30,
    cfg_override: dict | None = None,
    wordmark: str = "Service Delivery",
) -> Response:
    cfg = current_app.config.get(cfg_key) if cfg_override is None else cfg_override
    cfg = cfg or {}
    interval = int(
        current_app.config.get(interval_key, default_interval) or default_interval
    )
    reload_minutes = int(current_app.config.get("MOH_TV_RELOAD_MINUTES", 120) or 120)
    return Response(
        _render_tv_page(
            _tv_page_payload(
                cfg, interval, reload_minutes, _tv_options(wordmark)
            )
        ),
        mimetype="text/html",
    )


def _resolve_tv_preset(preset: str) -> tuple[dict, str, str] | None:
    """Return (slides_cfg, interval_key, wordmark) for a moh_tv= preset."""
    config = current_app.config
    if preset == "perf":
        return (
            config.get("MOH_TV_SLIDES_PERF") or {},
            "MOH_TV_INTERVAL_SECONDS_PERF",
            "Performance Monitoring",
        )
    if preset.startswith("group-"):
        slug = preset[6:]
        groups = config.get("MOH_TV_GROUPS") or {}
        if slug not in groups:
            return None
        return (
            groups[slug],
            "MOH_TV_INTERVAL_SECONDS",
            slug.replace("-", " ").title(),
        )
    return (
        config.get("MOH_TV_SLIDES") or {},
        "MOH_TV_INTERVAL_SECONDS",
        "Service Delivery",
    )


def _tv_redirect(preset: str, slides_cfg: dict) -> Response:
    return redirect(tv_embed_url(str(slides_cfg.get("dashboard") or ""), preset))


def _require_tv_login() -> Response | None:
    """Send anonymous TV requests to /login/ once; after that the dashboard
    opens in this same window (no iframe, so no second Sign-in form).
    """
    if getattr(current_user, "is_authenticated", False):
        return None
    nxt = request.full_path if request.query_string else request.path
    if nxt.endswith("?"):
        nxt = nxt[:-1]
    return redirect(f"/login/?next={nxt}")


@moh_assets_bp.route("/tv")
def tv_slideshow():
    """Send the wall TV to dashboard 8 in this window (one login)."""
    gate = _require_tv_login()
    if gate is not None:
        return gate
    resolved = _resolve_tv_preset("main")
    assert resolved is not None
    slides_cfg, _interval_key, _wordmark = resolved
    return _tv_redirect("main", slides_cfg)


@moh_assets_bp.route("/tv-perf")
def tv_slideshow_perf():
    """Send the wall TV to dashboard 3 in this window (one login)."""
    gate = _require_tv_login()
    if gate is not None:
        return gate
    resolved = _resolve_tv_preset("perf")
    assert resolved is not None
    slides_cfg, _interval_key, _wordmark = resolved
    return _tv_redirect("perf", slides_cfg)


@moh_assets_bp.route("/tv/group/<slug>")
def tv_group_slideshow(slug: str):
    """Send one dashboard-8 group to the wall TV in this window."""
    gate = _require_tv_login()
    if gate is not None:
        return gate
    resolved = _resolve_tv_preset(f"group-{slug}")
    if resolved is None:
        abort(404)
    slides_cfg, _interval_key, _wordmark = resolved
    return _tv_redirect(f"group-{slug}", slides_cfg)


@moh_assets_bp.route("/tv-config/<preset>")
def tv_config(preset: str) -> Response:
    """JSON for the same-window TV player. Auth required."""
    if not getattr(current_user, "is_authenticated", False):
        return jsonify({"error": "login required"}), 401
    resolved = _resolve_tv_preset(preset)
    if resolved is None:
        abort(404)
    slides_cfg, interval_key, wordmark = resolved
    interval = int(current_app.config.get(interval_key, 30) or 30)
    if preset == "perf":
        interval = int(
            current_app.config.get("MOH_TV_INTERVAL_SECONDS_PERF", interval) or interval
        )
    reload_minutes = int(current_app.config.get("MOH_TV_RELOAD_MINUTES", 120) or 120)
    return jsonify(
        _tv_page_payload(
            slides_cfg, interval, reload_minutes, _tv_options(wordmark)
        )
    )


@moh_assets_bp.route("/<path:filename>")
def serve_asset(filename: str):
    """Serve a whitelisted brand asset from the webpack-safe location.

    Uses a path converter so nested files (e.g. guide_images/01-login-page.png)
    resolve; the allowlist still rejects anything not explicitly listed.
    """
    if filename not in _ALLOWED_FILES:
        abort(404)
    resp = send_from_directory(_BRAND_ASSET_DIR, filename)
    if filename.endswith(".js"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


@moh_guide_bp.route("/guide/")
def user_guide():
    """Serve the MoH dashboard Help & User Guide (landing-page tile target)."""
    if not getattr(current_user, "is_authenticated", False):
        return redirect(f"/login/?next={request.path}")

    resp = make_response(render_template("superset/user_guide.html"))
    # The guide uses inline <style> and only same-origin assets.
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "script-src 'self' 'unsafe-inline'"
    )
    resp.headers.pop("X-Frame-Options", None)
    return resp


@moh_guide_bp.route("/feedback/")
def feedback():
    """Serve the MoH feedback page (Google Form embedded in an iframe)."""
    if not getattr(current_user, "is_authenticated", False):
        return redirect(f"/login/?next={request.path}")

    resp = make_response(render_template("superset/feedback.html"))
    # The page embeds a Google Form in an iframe, so frame-src must allow it.
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "script-src 'self' 'unsafe-inline'; "
        "frame-src https://docs.google.com"
    )
    resp.headers.pop("X-Frame-Options", None)
    return resp
