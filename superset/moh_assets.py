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

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
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


_TV_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MoH Dashboard TV</title>
<style>
  html, body { margin: 0; height: 100%; background: #000; overflow: hidden; }
  /* The iframe is laid out on a fixed canvas (1920x1080 by default) and that
     canvas is scaled to the screen. transform-origin top-left so the translate
     offsets below position it predictably. */
  #tv {
    position: absolute; top: 0; left: 0; border: 0;
    transform-origin: top left; background: #fff;
  }
  /* 22px: the same legibility floor the slides are held to. */
  #label {
    position: fixed; left: 16px; bottom: 12px; z-index: 10;
    font: 600 22px/1.2 system-ui, sans-serif; color: #fff;
    background: rgba(0,0,0,.45); padding: 6px 12px; border-radius: 8px;
    pointer-events: none;
  }
  #empty {
    position: fixed; inset: 0; display: flex; align-items: center;
    justify-content: center; color: #ccc;
    font: 400 18px/1.5 system-ui, sans-serif; text-align: center; padding: 24px;
  }
  #controls {
    position: fixed; bottom: 18px; left: 50%; transform: translateX(-50%);
    z-index: 20; display: flex; gap: 10px;
  }
  #controls button {
    font: 600 15px/1 system-ui, sans-serif; color: #fff;
    background: rgba(0,0,0,.5); border: 0; cursor: pointer;
    padding: 9px 18px; border-radius: 8px; opacity: .38;
    transition: opacity .25s;
  }
  #controls button:hover { opacity: 1; }
</style>
</head>
<body>
  <iframe id="tv" referrerpolicy="same-origin"></iframe>
  <div id="label"></div>
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
    const label = document.getElementById('label');
    const controls = document.getElementById('controls');
    const prevBtn = document.getElementById('prevBtn');
    const fsBtn = document.getElementById('fsBtn');
    const nextBtn = document.getElementById('nextBtn');

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
      let shrink = 1;       // <1 when the current slide is taller than the canvas
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

      function screenScale() {
        return Math.min(window.innerWidth / CANVAS_W, window.innerHeight / CANVAS_H);
      }

      function placeFrame(w, h, s) {
        const k = screenScale() * s;
        frame.style.width = w + 'px';
        frame.style.height = h + 'px';
        frame.style.transform =
          'translate(' + ((window.innerWidth - w * k) / 2) + 'px,'
          + ((window.innerHeight - h * k) / 2) + 'px) scale(' + k + ')';
      }

      function resetFrame() {
        placeFrame(CANVAS_W, CANVAS_H, 1);
      }

      function updateLabel(n) {
        const slide = CFG.slides[n === undefined ? i : n];
        const tall = shrink < 0.995;
        label.textContent = (slide && slide.label || '')
          + (tall ? ' · too tall, text at ' + Math.round(shrink * 100) + '%' : '');
        label.style.background = tall ? 'rgba(160,50,30,.9)' : '';
        if (tall && slide && !warned[slide.label]) {
          warned[slide.label] = true;
          console.warn('TV: "' + slide.label + '" is taller than the '
            + CANVAS_H + 'px canvas; text is shrunk to ' + Math.round(shrink * 100)
            + '%. Split or trim the slide.');
        }
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
          'html,body{height:auto!important;overflow:visible!important;margin:0!important;}' +
          '#app,.ant-layout,.ant-layout-content,.ant-layout-content>div,' +
          '.dashboard,.dashboard-content,.grid-content,[data-test="grid-content"]' +
          '{height:auto!important;max-height:none!important;overflow:visible!important;margin:0!important;padding:0!important;}' +
          '.dashboard{padding-top:0!important;margin-top:0!important;}' +
          'body{overflow:hidden!important;}' +
          '#main-menu, header.top, .navbar, .ant-layout-header, .dashboard-header-container,' +
          '[data-test="dashboard-header-wrapper"], .dashboard-header-container .header-with-actions' +
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

      // Lay the slide out on the fixed canvas and scale that canvas to the
      // screen. A slide that fits is drawn 1:1, so its text keeps the size the
      // TV theme gave it and does not change from slide to slide. The old
      // behaviour scaled every slide by its own height, so type size swung
      // with how tall each slide happened to be. Now only a slide taller than
      // the canvas is shrunk, just enough to be seen whole, and it is flagged
      // on the label so someone splits it.
      function fit() {
        const doc = safeDoc();
        if (!doc || !doc.body) return;
        unlockScroll(doc);
        hideTabBars(doc);
        wireIframeGestures();
        wireResizeObserver(doc);

        let s = 1;
        for (let n = 0; n < 4; n++) {
          const w = Math.round(CANVAS_W / s);
          if (Math.abs((parseFloat(frame.style.width) || 0) - w) >= 2) {
            frame.style.width = w + 'px';
          }
          s = Math.min(1, CANVAS_H / Math.max(contentHeight(doc), 1));
          if (Math.abs(Math.round(CANVAS_W / s) - w) < 2) break;
        }
        shrink = s;
        const w = Math.round(CANVAS_W / s);
        const h = Math.max(Math.round(contentHeight(doc)), Math.ceil(CANVAS_H / s));
        placeFrame(w, h, s);
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
        shrink = 1;
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

      frame.addEventListener('load', () => {
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
    axis_label = {"fontSize": chart, "hideOverlap": True}
    return {
        "token": {"fontSize": floor},
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


def _tv_options() -> dict[str, Any]:
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
            {"path": [str(p) for p in s.get("path", [])],
             "label": str(s.get("label", "") or "")}
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
) -> Response:
    cfg = current_app.config.get(cfg_key) if cfg_override is None else cfg_override
    cfg = cfg or {}
    interval = int(
        current_app.config.get(interval_key, default_interval) or default_interval
    )
    reload_minutes = int(current_app.config.get("MOH_TV_RELOAD_MINUTES", 120) or 120)
    return Response(
        _render_tv_page(
            _tv_page_payload(cfg, interval, reload_minutes, _tv_options())
        ),
        mimetype="text/html",
    )


@moh_assets_bp.route("/tv")
def tv_slideshow():
    """Full-screen rotating slideshow (dashboard 8) for a wall TV."""
    return _tv_response("MOH_TV_SLIDES", "MOH_TV_INTERVAL_SECONDS")


@moh_assets_bp.route("/tv-perf")
def tv_slideshow_perf():
    """Full-screen rotating slideshow (dashboard 3, Summary sub-tabs) for a wall TV."""
    return _tv_response("MOH_TV_SLIDES_PERF", "MOH_TV_INTERVAL_SECONDS_PERF")


@moh_assets_bp.route("/tv/group/<slug>")
def tv_group_slideshow(slug: str):
    """Themed TV slideshow: one dashboard-8 tab group per wall TV.

    Groups are defined in the MOH_TV_GROUPS config dict, keyed by slug.
    """
    groups = current_app.config.get("MOH_TV_GROUPS") or {}
    if slug not in groups:
        abort(404)
    return _tv_response(
        "MOH_TV_GROUPS", "MOH_TV_INTERVAL_SECONDS", cfg_override=groups[slug]
    )


@moh_assets_bp.route("/<path:filename>")
def serve_asset(filename: str):
    """Serve a whitelisted brand asset from the webpack-safe location.

    Uses a path converter so nested files (e.g. guide_images/01-login-page.png)
    resolve; the allowlist still rejects anything not explicitly listed.
    """
    if filename not in _ALLOWED_FILES:
        abort(404)
    return send_from_directory(_BRAND_ASSET_DIR, filename)


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
