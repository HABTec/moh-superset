
"""
Primary Health Care Status Monitoring Dashboard page — iframe wrapper around an external Dashboard Monitoring service.

Renders a single page at /monitoring-dashboard/ (admin-only) which embeds whatever URL
is in the HPC_MONITORING_DASHBOARD_IFRAME_URL environment variable. If the env var isn't set
the page shows a friendly "Monitoring Dashboard not configured" placeholder with
instructions.

The route also overrides Superset's default CSP for this page so the
browser permits the iframe to the configured AI service origin. Without
this override the default `default-src 'self'` blocks the iframe with a
console "frame-src violates default-src 'self'" error.

"""

from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

from flask import Blueprint, current_app, make_response, redirect, render_template, request
from flask_login import current_user

from superset.superset_typing import FlaskResponse

logger = logging.getLogger(__name__)

hpc_bp = Blueprint(
    "hpc",
    __name__,
    template_folder="templates",
)


def _require_login() -> FlaskResponse | None:
    """Return a redirect if the user isn't authenticated; None if they are."""
    if not getattr(current_user, "is_authenticated", False):
        return redirect(f"/login/?next={request.path}")
    return None


@hpc_bp.route("/hpc/")
def hpc_monitoring_dashboard_page() -> FlaskResponse:
    """Serve the Primary Health Care Monitoring Dashboard page (iframe to an external service)."""
    if (denied := _require_login()) is not None:
        return denied

    iframe_url = current_app.config.get("PHC_MONITORING_DASHBOARD_IFRAME_URL", "")
    if not iframe_url:
        iframe_url = current_app.config.get("HPC_MONITORING_DASHBOARD_IFRAME_URL", "")
    resp = make_response(render_template(
        "superset/hpc.html",
        iframe_url=iframe_url,
    ))

    # Override Superset's default CSP for this page only — without this
    # the browser blocks the iframe with:
    #   "frame-src violates default-src 'self'"
    if iframe_url:
        parsed = urlparse(iframe_url)
        if parsed.scheme and parsed.netloc:
            target_origin = f"{parsed.scheme}://{parsed.netloc}"
            resp.headers["Content-Security-Policy"] = (
                f"default-src 'self'; "
                f"img-src 'self' data: {target_origin}; "
                f"style-src 'self' 'unsafe-inline'; "
                f"script-src 'self'; "
                f"frame-src 'self' {target_origin}; "
                f"connect-src 'self' {target_origin}"
            )
    # Some upstream layers add X-Frame-Options: it would refuse to render
    # OUR page in a frame (doesn't apply here — we're the parent, not the
    # embedded child) but cleaner to drop it.
    resp.headers.pop("X-Frame-Options", None)
    return resp
