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
</style>
</head>
<body>
  <iframe id="tv" referrerpolicy="same-origin"></iframe>
  <div id="label"></div>
  <div id="hint">Tap the screen (or press any key) for fullscreen</div>
  <script>
    const SLIDES = __SLIDES__;
    const INTERVAL_MS = __INTERVAL__ * 1000;
    const frame = document.getElementById('tv');
    const label = document.getElementById('label');
    const hint = document.getElementById('hint');

    // Hide the browser chrome: request fullscreen on load, and again on the
    // first tap/key — browsers require a user gesture before allowing it.
    function goFullscreen() {
      const el = document.documentElement;
      const fn = el.requestFullscreen || el.webkitRequestFullscreen
        || el.mozRequestFullScreen || el.msRequestFullscreen;
      if (fn && !document.fullscreenElement && !document.webkitFullscreenElement) {
        try { fn.call(el); } catch (e) { /* needs gesture; hint stays */ }
      }
    }
    function syncHint() {
      hint.style.display =
        (document.fullscreenElement || document.webkitFullscreenElement)
          ? 'none' : 'block';
    }
    goFullscreen();
    document.addEventListener('fullscreenchange', syncHint);
    document.addEventListener('webkitfullscreenchange', syncHint);
    document.addEventListener('click', goFullscreen);
    document.addEventListener('touchstart', goFullscreen);
    document.addEventListener('keydown', goFullscreen);

    if (!SLIDES.length) {
      document.body.innerHTML =
        '<div id="empty">No TV slides configured.<br>'
        + 'Set MOH_TV_SLIDES in superset_config.py.</div>';
    } else {
      let i = -1;
      let fitTimers = [];

      // Render the dashboard at the TV's pixel width, tall enough that nothing
      // is clipped, then scale it down so the whole tab fits the screen.
      function designWidth() { return window.innerWidth; }

      function resetFrame() {
        frame.style.transform = 'none';
        frame.style.width = designWidth() + 'px';
        // Start at the window height (NOT a huge value — that would make the
        // measured content height wrong and shrink everything to a sliver).
        frame.style.height = window.innerHeight + 'px';
      }

      // Make the dashboard flow to its natural height inside the iframe instead
      // of scrolling in a fixed-height container, so we can measure + show it all.
      function unlockScroll(doc) {
        if (doc.getElementById('moh-tv-unlock')) return;
        const st = doc.createElement('style');
        st.id = 'moh-tv-unlock';
        st.textContent =
          'html,body{height:auto!important;overflow:visible!important;margin:0!important;}' +
          '#app,.ant-layout,.ant-layout-content,.ant-layout-content>div,' +
          '.dashboard,.dashboard-content,.grid-content,[data-test="grid-content"]' +
          '{height:auto!important;max-height:none!important;overflow:visible!important;margin:0!important;padding:0!important;}' +
          '#main-menu, header.top, .navbar, .ant-layout-header, .dashboard-header-container,' +
          '[data-test="dashboard-header-wrapper"], .dashboard-header-container .header-with-actions,' +
          '.ant-tabs-nav, .ant-tabs-nav-wrap, .ant-tabs-nav-list {display:none!important;}' +
          '.dashboard{padding-top:0!important;margin-top:0!important;}' +
          'body{overflow:hidden!important;}' +
          // Superset caps the content column at viewport-minus-filter-bar even
          // when the bar is hidden — lift every internal width cap so charts
          // span the full frame, otherwise side bands show on wide TVs.
          '.dashboard,.dashboard-content,[data-test="dashboard-content"],' +
          '[class*="dashboard-builder"],.grid-content,[data-test="grid-content"],' +
          '.dashboard-grid{max-width:none!important;width:auto!important;}';
        (doc.head || doc.documentElement).appendChild(st);
      }

      function contentHeight(doc) {
        // Prefer the dashboard grid's own content height. Do NOT max() with
        // body.scrollHeight — the body can be inflated to the iframe's height
        // and would throw the scale off (shrinking everything to a sliver).
        const grid = doc.querySelector('[data-test="grid-content"]')
          || doc.querySelector('.grid-content')
          || doc.querySelector('.dashboard-grid');
        if (grid && grid.scrollHeight > 40) return grid.scrollHeight;
        return (doc.body && doc.body.scrollHeight) || window.innerHeight;
      }

      // Fill the whole screen — no letterbox bars. Solve the scale that maps
      // content height onto screen height, then set the frame width to
      // innerWidth / scale so the scaled width lands exactly on the screen
      // width. Content reflows when the width changes, so re-measure until
      // stable before committing the transform.
      function fit() {
        let doc;
        try { doc = frame.contentDocument; } catch (e) { return; }   // cross-origin
        if (!doc || !doc.body) return;
        unlockScroll(doc);
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

        // Overshoot ~0.3% and centre-crop the remainder so rounding never
        // leaves a hairline gap on any edge.
        s *= 1.003;
        const w = Math.max(320, Math.round(vw / s));
        const h = Math.round(contentHeight(doc));
        frame.style.width = w + 'px';
        frame.style.height = h + 'px';
        const left = (vw - w * s) / 2;
        const top = (vh - h * s) / 2;
        frame.style.transform =
          'translate(' + left + 'px,' + top + 'px) scale(' + s + ')';
      }

      function scheduleFit() {
        fitTimers.forEach(clearTimeout);
        // Charts render asynchronously — re-fit a few times as content settles.
        fitTimers = [2000, 4000, 7000, 11000].map(t => setTimeout(fit, t));
      }

      function show(n) {
        const s = SLIDES[n];
        resetFrame();
        // Force a full reload (and tab switch) even when only the #TAB hash
        // differs, by varying a throwaway param.
        const u = new URL(s.url, window.location.origin);
        u.searchParams.set('_tv', String(Date.now()));
        // Always start with the native filter bar collapsed — do not depend on
        // the deployment's FILTERBAR_CLOSED_BY_DEFAULT feature flag.
        u.searchParams.set('expand_filters', 'false');
        frame.src = u.toString();
        label.textContent = s.label || '';
      }

      function next() { i = (i + 1) % SLIDES.length; show(i); }

      frame.addEventListener('load', scheduleFit);
      window.addEventListener('resize', fit);
      next();
      if (SLIDES.length > 1) setInterval(next, INTERVAL_MS);
    }
  </script>
</body>
</html>
"""


def _normalize_slides(raw: list) -> list[dict]:
    """Convert [["<url>", "<label>"], ...] entries to slide dicts."""
    return [
        {"url": str(item[0]), "label": str(item[1]) if len(item) > 1 else ""}
        for item in raw
        if item and item[0]
    ]


def _tv_page_html(slides_key: str, interval_key: str, default_interval: int = 30) -> str:
    """Render the TV slideshow page for the given config keys.

    Each slide is ["<dashboard url with ?standalone=2#TAB-...>", "<label>"].
    """
    interval = int(current_app.config.get(interval_key, default_interval) or default_interval)
    slides = _normalize_slides(current_app.config.get(slides_key) or [])
    return _TV_PAGE.replace("__SLIDES__", json.dumps(slides)).replace(
        "__INTERVAL__", str(interval)
    )


@moh_assets_bp.route("/tv")
def tv_slideshow():
    """Full-screen rotating slideshow (dashboard 8) for a wall TV."""
    return Response(
        _tv_page_html("MOH_TV_SLIDES", "MOH_TV_INTERVAL_SECONDS"),
        mimetype="text/html",
    )


@moh_assets_bp.route("/tv-perf")
def tv_slideshow_perf():
    """Full-screen rotating slideshow (dashboard 3, Summary sub-tabs) for a wall TV."""
    return Response(
        _tv_page_html("MOH_TV_SLIDES_PERF", "MOH_TV_INTERVAL_SECONDS_PERF"),
        mimetype="text/html",
    )


@moh_assets_bp.route("/tv/group/<slug>")
def tv_group_slideshow(slug: str):
    """Themed TV slideshow: one dashboard-8 tab group per wall TV.

    Groups are defined in the MOH_TV_GROUPS config dict, keyed by slug.
    """
    groups = current_app.config.get("MOH_TV_GROUPS") or {}
    raw = groups.get(slug)
    if not raw:
        abort(404)
    interval = int(
        current_app.config.get("MOH_TV_INTERVAL_SECONDS", 30) or 30
    )
    html = _TV_PAGE.replace("__SLIDES__", json.dumps(_normalize_slides(raw))).replace(
        "__INTERVAL__", str(interval)
    )
    return Response(html, mimetype="text/html")


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
