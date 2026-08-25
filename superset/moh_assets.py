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
  /* The iframe is rendered at full TV width, then scaled+centred to fit the
     whole tab on screen (no scrolling on a TV). transform-origin top-left so the
     translate offsets below position it predictably. */
  #tv {
    position: absolute; top: 0; left: 0; border: 0;
    transform-origin: top left; background: #fff;
  }
  #label {
    position: fixed; left: 16px; bottom: 12px; z-index: 10;
    font: 600 16px/1.2 system-ui, sans-serif; color: #fff;
    background: rgba(0,0,0,.45); padding: 6px 12px; border-radius: 8px;
    pointer-events: none;
  }
  #empty {
    position: fixed; inset: 0; display: flex; align-items: center;
    justify-content: center; color: #ccc;
    font: 400 18px/1.5 system-ui, sans-serif; text-align: center; padding: 24px;
  }
  #hint {
    position: fixed; right: 16px; bottom: 12px; z-index: 10;
    font: 500 14px/1.2 system-ui, sans-serif; color: #fff;
    background: rgba(0,0,0,.45); padding: 6px 12px; border-radius: 8px;
    pointer-events: none;
  }
  #fsbtn {
    position: fixed; right: 16px; top: 12px; z-index: 20;
    font: 600 14px/1 system-ui, sans-serif; color: #fff;
    background: rgba(0,0,0,.45); border: 0; cursor: pointer;
    padding: 8px 14px; border-radius: 8px; opacity: .55;
  }
  #fsbtn:hover { opacity: 1; }
</style>
</head>
<body>
  <iframe id="tv" referrerpolicy="same-origin"></iframe>
  <div id="label"></div>
  <div id="hint">Tap the screen (or press any key) for fullscreen</div>
  <button id="fsbtn" type="button">⛶ Fullscreen</button>
  <script>
    const CFG = __CONFIG__;
    const frame = document.getElementById('tv');
    const label = document.getElementById('label');
    const hint = document.getElementById('hint');
    const fsbtn = document.getElementById('fsbtn');

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
    function syncHint() {
      const full =
        !!(document.fullscreenElement || document.webkitFullscreenElement);
      hint.style.display = full ? 'none' : 'block';
      fsbtn.style.display = full ? 'none' : 'block';
    }
    goFullscreen();
    document.addEventListener('fullscreenchange', syncHint);
    document.addEventListener('webkitfullscreenchange', syncHint);
    fsbtn.addEventListener('click', e => { e.stopPropagation(); toggleFullscreen(); });
    document.addEventListener('keydown', goFullscreen);

    // Taps inside the iframe never reach this document (the dashboard fills
    // it completely), so listen there too — same-origin makes that possible.
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

      const sleep = ms => new Promise(r => setTimeout(r, ms));

      function resetFrame() {
        frame.style.transform = 'none';
        frame.style.width = window.innerWidth + 'px';
        frame.style.height = window.innerHeight + 'px';
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

      // Fill the whole screen — no letterbox bars. Solve the scale that maps
      // content height onto screen height, then size the frame width to
      // innerWidth / scale so the scaled width lands exactly on screen width.
      function fit() {
        const doc = safeDoc();
        if (!doc || !doc.body) return;
        unlockScroll(doc);
        hideTabBars(doc);
        wireIframeGestures();
        const vw = window.innerWidth;
        const vh = window.innerHeight;

        let s = vh / contentHeight(doc);
        for (let k = 0; k < 4; k++) {
          const w = Math.max(320, Math.round(vw / s));
          if (Math.abs((parseFloat(frame.style.width) || 0) - w) < 2) break;
          frame.style.width = w + 'px';
          s = vh / contentHeight(doc);
        }
        s = Math.min(Math.max(s, 0.25), 5);

        // Overshoot ~0.3% and centre-crop so rounding never leaves a gap.
        s *= 1.003;
        const w = Math.max(320, Math.round(vw / s));
        const h = Math.round(contentHeight(doc));
        frame.style.width = w + 'px';
        frame.style.height = h + 'px';
        frame.style.transform =
          'translate(' + ((vw - w * s) / 2) + 'px,' + ((vh - h * s) / 2)
          + 'px) scale(' + s + ')';
      }

      function scheduleFit() {
        fitTimers.forEach(clearTimeout);
        fitTimers = [800, 2000, 4000, 7000].map(t => setTimeout(fit, t));
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

      async function run(n) {
        const my = ++token;
        label.textContent = CFG.slides[n].label || '';
        resetFrame();

        const doc = safeDoc();
        const ready = doc &&
          doc.querySelector('[data-test="grid-content"],.grid-content,.dashboard-grid');
        if (!ready) { pending = n; frame.src = bust(CFG.url); return; }

        try {
          if (await clickPath(CFG.slides[n].path, my) && my === token) {
            scheduleFit();
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

      function next() { i = (i + 1) % CFG.slides.length; run(i); }
      next();
      setInterval(next, CFG.intervalMs);
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


def _tv_page_payload(
    slides_cfg: dict, interval_seconds: int, reload_minutes: int
) -> dict:
    """Build the JSON payload consumed by the TV page script.

    slides_cfg shape:
        {"dashboard": "/superset/dashboard/8/?standalone=2",
         "slides": [{"path": ["Services Delivery", "NCD"], "label": "NCD"}, ...]}
    Slides reference TABS BY TITLE PATH instead of URL, so switching happens
    by clicking tabs inside one live iframe — no page reload per slide.
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
        _render_tv_page(_tv_page_payload(cfg, interval, reload_minutes)),
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
