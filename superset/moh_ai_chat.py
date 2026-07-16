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
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import jwt
from flask import (
    Blueprint,
    current_app,
    has_app_context,
    make_response,
    redirect,
    render_template,
    request,
)
from flask_login import current_user

from superset.superset_typing import FlaskResponse

logger = logging.getLogger(__name__)

ai_chat_bp = Blueprint(
    "moh_ai_chat",
    __name__,
    template_folder="templates",
)


def _require_login() -> FlaskResponse | None:
    """Return a redirect if the user isn't authenticated; None if they are."""
    if not getattr(current_user, "is_authenticated", False):
        return redirect(f"/login/?next={request.path}")
    return None


def _get_config_value(name: str, default: object = "") -> object:
    """Read a value from Flask config first, then fall back to the environment."""
    if has_app_context() and current_app.config.get(name) is not None:
        return current_app.config.get(name, default)
    return os.environ.get(name, default)


def _build_ai_chat_url(iframe_url: str, user: object) -> str:
    """Return an iframe URL that includes a signed JWT when configured."""
    secret = str(_get_config_value("AUTH_JWT_SECRET", "")).strip()
    algorithm = str(_get_config_value("AUTH_JWT_ALGORITHM", "HS256")).strip() or "HS256"
    expire_minutes = str(_get_config_value("AUTH_JWT_EXPIRE_MINUTES", "")).strip()

    if not secret:
        return iframe_url

    try:
        expire_minutes_value = int(expire_minutes) if expire_minutes else 1440
    except ValueError:
        expire_minutes_value = 1440

    now = datetime.now(timezone.utc)
    claims = {
        "sub": getattr(user, "username", None) or getattr(user, "email", None),
        "email": getattr(user, "email", None),
        "role": "admin" if _is_admin_user(user) else "user",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expire_minutes_value)).timestamp()),
    }
    token = jwt.encode(claims, secret, algorithm=algorithm)

    parsed = urlparse(iframe_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["token"] = token
    return urlunparse(
        parsed._replace(query=urlencode(query, doseq=True))
    )


def _is_admin_user(user: object) -> bool:
    """Determine whether the user should be treated as an admin."""
    admin_emails_value = _get_config_value("AUTH_ADMIN_EMAILS", "")
    if isinstance(admin_emails_value, (list, tuple, set)):
        admin_emails = {str(email).strip().lower() for email in admin_emails_value if str(email).strip()}
    else:
        admin_emails = {
            email.strip().lower()
            for email in str(admin_emails_value).split(",")
            if email.strip()
        }
    email = getattr(user, "email", None)
    if isinstance(email, str) and email.lower() in admin_emails:
        return True

    username = getattr(user, "username", None)
    if isinstance(username, str) and username.lower() in {"admin", "root"}:
        return True

    return False


@ai_chat_bp.route("/ai-chat/")
def ai_chat_page() -> FlaskResponse:
    """Serve the AI Assistant page (iframe to an external service)."""
    if (denied := _require_login()) is not None:
        return denied

    iframe_url = os.environ.get("MOH_AI_IFRAME_URL", "")
    signed_iframe_url = _build_ai_chat_url(iframe_url, current_user)
    resp = make_response(render_template(
        "superset/ai_chat.html",
        iframe_url=signed_iframe_url,
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
