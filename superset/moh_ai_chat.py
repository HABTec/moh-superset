# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.
"""
MoH AI Assistant page — iframe wrapper around an external AI service.

Renders a single page at /ai-chat/ (admin-only) which embeds whatever URL
is in the MOH_AI_IFRAME_URL environment variable. If the env var isn't set
the page shows a friendly "AI Assistant not configured" placeholder with
instructions.

The route also overrides Superset's default CSP for this page so the
browser permits the iframe to the configured AI service origin. Without
this override the default `default-src 'self'` blocks the iframe with a
console "frame-src violates default-src 'self'" error.

Registered with Flask via the BLUEPRINTS list in superset/moh_branding.py.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

from flask import Blueprint, abort, make_response, redirect, render_template, request
from flask_login import current_user

from superset.extensions import security_manager
from superset.superset_typing import FlaskResponse

logger = logging.getLogger(__name__)

ai_chat_bp = Blueprint(
    "moh_ai_chat",
    __name__,
    template_folder="templates",
)


def _require_admin() -> FlaskResponse | None:
    """Return a redirect/abort if the user isn't an admin; None if they are.

    Unauthenticated → redirect to /login with next=current path.
    Authenticated non-admin → 403.
    """
    if not getattr(current_user, "is_authenticated", False):
        return redirect(f"/login/?next={request.path}")
    if not security_manager.is_admin():
        abort(403)
    return None


@ai_chat_bp.route("/ai-chat/")
def ai_chat_page() -> FlaskResponse:
    """Serve the AI Assistant page (iframe to an external service)."""
    if (denied := _require_admin()) is not None:
        return denied

    iframe_url = os.environ.get("MOH_AI_IFRAME_URL", "")
    resp = make_response(render_template(
        "superset/ai_chat.html",
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
