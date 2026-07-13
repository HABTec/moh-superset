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

from flask import Blueprint, Response, abort, current_app, send_from_directory

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
</style>
</head>
<body>
  <iframe id="tv" referrerpolicy="same-origin"></iframe>
  <div id="label"></div>
  <script>
    const SLIDES = __SLIDES__;
    const INTERVAL_MS = __INTERVAL__ * 1000;
    const frame = document.getElementById('tv');
    const label = document.getElementById('label');

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
          'html,body{height:auto!important;overflow:visible!important;}' +
          '#app,.ant-layout,.ant-layout-content,.ant-layout-content>div,' +
          '.dashboard,.dashboard-content,.grid-content,[data-test="grid-content"]' +
          '{height:auto!important;max-height:none!important;overflow:visible!important;}';
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

      function fit() {
        let doc;
        try { doc = frame.contentDocument; } catch (e) { return; }   // cross-origin
        if (!doc || !doc.body) return;
        unlockScroll(doc);
        const w = designWidth();
        const h = contentHeight(doc);
        frame.style.width = w + 'px';
        frame.style.height = h + 'px';
        const s = Math.min(window.innerWidth / w, window.innerHeight / h);
        const left = (window.innerWidth - w * s) / 2;
        const top = (window.innerHeight - h * s) / 2;
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


@moh_assets_bp.route("/tv")
def tv_slideshow():
    """Full-screen rotating slideshow of configured dashboard tabs for a wall TV.

    Reads MOH_TV_INTERVAL_SECONDS and MOH_TV_SLIDES from config (env-driven).
    Each slide is ["<dashboard url with ?standalone=2#TAB-...>", "<label>"].
    """
    interval = int(current_app.config.get("MOH_TV_INTERVAL_SECONDS", 30) or 30)
    raw = current_app.config.get("MOH_TV_SLIDES") or []
    slides = [
        {"url": str(item[0]), "label": str(item[1]) if len(item) > 1 else ""}
        for item in raw
        if item and item[0]
    ]
    html = _TV_PAGE.replace("__SLIDES__", json.dumps(slides)).replace(
        "__INTERVAL__", str(interval)
    )
    return Response(html, mimetype="text/html")


@moh_assets_bp.route("/<filename>")
def serve_asset(filename: str):
    """Serve a whitelisted brand asset from the webpack-safe location."""
    if filename not in _ALLOWED_FILES:
        abort(404)
    return send_from_directory(_BRAND_ASSET_DIR, filename)
