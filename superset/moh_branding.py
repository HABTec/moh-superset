# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.
"""
MoH branding & theme customizations.

Single source of truth for the MoH-specific Superset overrides. Imported by
both the Docker dev config (`docker/pythonpath_dev/superset_config_docker.py`)
and any native install on Ubuntu/server (where you'd point Superset's
SUPERSET_CONFIG_PATH at a tiny `superset_config.py` that does
`from superset.moh_branding import *`).

Edit this file to change branding everywhere — no docker-only files involved.
"""

from superset.config import (
    THEME_DARK as _APACHE_THEME_DARK,
    THEME_DEFAULT as _APACHE_THEME_DEFAULT,
)

import os as _os
from urllib.parse import urlparse as _urlparse

# ---------------------------------------------------------------------------
# Version & app identity
# ---------------------------------------------------------------------------
VERSION_STRING = "MoH 6.0"
APP_NAME = "MoH Analytics Portal"

# Logo shown in the top-left of every Superset page.
# Served by superset/moh_assets.py from superset/templates/superset/ — that
# directory survives `npm run build` (webpack cleans `static/assets/` but
# leaves `templates/` alone), so the logo doesn't disappear after deploys.
APP_ICON = "/moh-static/logomohnewww.png"
APP_ICON_WIDTH = 150
LOGO_TARGET_PATH = "/"
LOGO_TOOLTIP = "MoH Analytics Portal"
LOGO_RIGHT_TEXT = ""
# Favicon shown in browser tabs. Use the same webpack-safe static path
# as the spinner so it survives `npm run build`.
FAVICONS = [{"href": "/moh-static/moh_icon.png"}]

# ---------------------------------------------------------------------------
# Theme — extends Apache's THEME_DEFAULT so we don't lose any built-in tokens.
# This is the var Superset 6.x actually reads. It gets seeded into the DB as
# the system "THEME_DEFAULT" theme record on every app startup; the React top
# nav reads brandLogoUrl from the active theme, not from APP_ICON directly.
# ---------------------------------------------------------------------------
_MOH_BRAND_TOKENS = {
    "brandLogoUrl":    APP_ICON,
    "brandLogoAlt":    "Ministry of Health",
    "brandAppName":    APP_NAME,
    "brandLogoHref":   "/",
    "brandLogoHeight": "32px",
    # Loading spinner — shown while pages / dashboards / charts are loading.
    # Setting brandSpinnerUrl replaces Superset's default animated spinner
    # with the MoH icon. Served by superset/moh_assets.py from a webpack-safe
    # location so it survives `npm run build`.
    "brandSpinnerUrl": "/moh-static/moh_icon.png",
    # MoH primary colour — applies to buttons, links, active states everywhere
    "colorPrimary":    "#1a5cff",
    "colorLink":       "#1a5cff",
}

THEME_DEFAULT = {
    **_APACHE_THEME_DEFAULT,
    "token": {**_APACHE_THEME_DEFAULT["token"], **_MOH_BRAND_TOKENS},
}

THEME_DARK = {
    **_APACHE_THEME_DARK,
    "token": {**_APACHE_THEME_DARK["token"], **_MOH_BRAND_TOKENS},
} if _APACHE_THEME_DARK else None

# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------
FEATURE_FLAGS = {
    "ALERT_REPORTS": True,
    "DATASET_FOLDERS": True,
    "ENABLE_TEMPLATE_PROCESSING": True,
    "ENABLE_JAVASCRIPT_CONTROLS": True,
    "EMBEDDED_SUPERSET": True,
    "ENABLE_GEOCODE": True,
    "GUEST_TOKEN_JWT_ALGO": "HS256",
    "GLOBAL_ASYNC_QUERIES": True,     # charts load in parallel, not sequentially

}

# ---------------------------------------------------------------------------
# Alerts & Reports
# ---------------------------------------------------------------------------
# ALERT_REPORTS (above) turns the feature on in the UI, but it only fires when
# (a) Celery beat runs the "reports.scheduler" task — see beat_schedule in the
# CeleryConfig of superset_config(.example).py — and (b) delivery + a screenshot
# engine are configured here. Secrets always come from env vars.

# Deliver for real. If True, the worker only logs what it *would* send.
ALERT_REPORTS_NOTIFICATION_DRY_RUN = (
    _os.environ.get("ALERT_REPORTS_DRY_RUN", "false").lower() == "true"
)

# Internal URL the headless browser uses to reach THIS Superset for screenshots;
# the public link in the email uses WEBDRIVER_BASEURL_USER_FRIENDLY.
WEBDRIVER_BASEURL = _os.environ.get("WEBDRIVER_BASEURL", "http://localhost:8088/")
WEBDRIVER_BASEURL_USER_FRIENDLY = _os.environ.get("MOH_PUBLIC_URL", WEBDRIVER_BASEURL)

# Screenshot engine (alerts/reports image attachments + thumbnails). Either:
#   1. Playwright + Chromium (recommended on servers): set MOH_USE_PLAYWRIGHT=true
#      and run once: pip install playwright && playwright install chromium --with-deps
#   2. Selenium + headless Chrome/Firefox installed on the host (default below).
if _os.environ.get("MOH_USE_PLAYWRIGHT", "false").lower() == "true":
    FEATURE_FLAGS["PLAYWRIGHT_REPORTS_AND_THUMBNAILS"] = True
else:
    WEBDRIVER_TYPE = _os.environ.get("WEBDRIVER_TYPE", "chrome")
    WEBDRIVER_OPTION_ARGS = [
        "--headless",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--window-size=1920,1080",
    ]

# Email (SMTP) — required for email alerts/reports.
SMTP_HOST = _os.environ.get("SMTP_HOST", "localhost")
SMTP_PORT = int(_os.environ.get("SMTP_PORT", "587"))
SMTP_STARTTLS = _os.environ.get("SMTP_STARTTLS", "true").lower() == "true"
SMTP_SSL = _os.environ.get("SMTP_SSL", "false").lower() == "true"
SMTP_USER = _os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = _os.environ.get("SMTP_PASSWORD", "")
SMTP_MAIL_FROM = _os.environ.get("SMTP_MAIL_FROM", "alerts@moh.gov.et")
EMAIL_NOTIFICATIONS = True

# Slack (optional) — for alerts/reports that notify a Slack channel.
SLACK_API_TOKEN = _os.environ.get("SLACK_API_TOKEN") or None
# Both are env-driven, no hardcoded fallbacks — set them in docker/.env-local
# (for compose) or systemd EnvironmentFile / shell export (for native).
_MOH_CSP_DEV_ORIGIN = _os.environ.get("MOH_CSP_DEV_ORIGIN")
_MOH_AI_IFRAME_URL = _os.environ.get("MOH_AI_IFRAME_URL")

def _origin_of(url: str | None) -> str | None:
    if not url:
        return None
    p = _urlparse(url)
    if p.scheme and p.netloc:
        return f"{p.scheme}://{p.netloc}"
    # fallback: return the raw value (may already be an origin)
    return url

_MOH_CSP_DEV_ORIGIN = _origin_of(_MOH_CSP_DEV_ORIGIN)
_MOH_AI_IFRAME_ORIGIN = _origin_of(_MOH_AI_IFRAME_URL)

# Combine dev origin and optional AI iframe origin into lists used by the
# content security policy. This lets you set MOH_CSP_DEV_ORIGIN for local
# webpack/dev servers and/or MOH_AI_IFRAME_URL for an embedded AI service.
_MOH_CSP_EXTRA_ORIGINS = [o for o in (_MOH_CSP_DEV_ORIGIN, _MOH_AI_IFRAME_ORIGIN) if o]

_MOH_CSP = {
    "default-src": ["'self'"],
    "img-src": ["'self'", "data:"] + _MOH_CSP_EXTRA_ORIGINS,
    "style-src": ["'self'", "'unsafe-inline'"],
    "script-src": ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
    "font-src": ["'self'", "data:"],
    "frame-src": ["'self'"] + _MOH_CSP_EXTRA_ORIGINS,
    "frame-ancestors": ["'self'"],
    "connect-src": ["'self'"] + _MOH_CSP_EXTRA_ORIGINS,
    "worker-src": ["'self'", "blob:"],
}

# Dev: HTTP allowed, cookies not secure (local / VirtualBox use)
TALISMAN_DEV_CONFIG = {
    "force_https": False,
    "session_cookie_secure": False,
    "content_security_policy": _MOH_CSP,
}

# Production: enforce HTTPS and secure cookies.
# superset_config.py should reference TALISMAN_CONFIG (not TALISMAN_DEV_CONFIG)
# when deploying behind nginx+TLS. Set MOH_FORCE_HTTPS=false to keep HTTP
# (e.g. when TLS is terminated at a load balancer upstream).
TALISMAN_CONFIG = {
    "force_https": _os.environ.get("MOH_FORCE_HTTPS", "true").lower() == "true",
    "session_cookie_secure": _os.environ.get("MOH_FORCE_HTTPS", "true").lower() == "true",
    "content_security_policy": _MOH_CSP,
}
# ---------------------------------------------------------------------------
# MCP server (dev mode)
# ---------------------------------------------------------------------------
MCP_AUTH_ENABLED = False
MCP_DEV_USERNAME = "admin"


# Show every MCP tool to the model directly instead of hiding them behind a
# `search_tools` / `call_tool` meta-interface. Tool search is great for token
# economy with very large catalogs, but with summary mode the model can't see
# real tool names like `execute_sql` and ends up hallucinating names like
# `run_code` (which then fail with "Unknown tool"). Listing everything upfront
# costs ~15-20K extra tokens per turn — acceptable for our admin-only AI page.
MCP_TOOL_SEARCH_CONFIG = {"enabled": False}

# ---------------------------------------------------------------------------
# AI Assistant page (admin-only chat at /ai-chat/)
# Registers the Flask blueprint Superset will mount at app start. The page
# itself is gated on admin role at request time inside the blueprint.
# ---------------------------------------------------------------------------
from superset.moh_ai_chat import ai_chat_bp as _ai_chat_bp  # noqa: E402

# ---------------------------------------------------------------------------
# DHIS2 org-unit-tree adapter (read-only API under /api/v1/moh/dhis2/...)
# Feeds the @dhis2/ui OrganisationUnitTree component used by the custom
# Native Filter plugin. Defaults match the registered "MOH_Click_Hhouse"
# Superset DB connection; override any of these in your config to retarget:
#     MOH_ORG_UNITS_DB_NAME, MOH_ORG_UNITS_SCHEMA, MOH_ORG_UNITS_TABLE,
#     MOH_ORG_UNITS_ROOT_LEVEL, MOH_ORG_UNITS_MAX_LEVEL
# ---------------------------------------------------------------------------
from superset.hpc import hpc_bp as _hpc_bp  # noqa: E402
from superset.moh_orgunits_api import moh_orgunits_bp as _moh_orgunits_bp  # noqa: E402

MOH_ORG_UNITS_DB_NAME = "MOH_Click_Hhouse"
MOH_ORG_UNITS_SCHEMA = "moh"
MOH_ORG_UNITS_TABLE = "org_units"
MOH_ORG_UNITS_ROOT_LEVEL = 2  # 2 = Region (start tree at the 14 Ethiopian regions)
MOH_ORG_UNITS_MAX_LEVEL = 6   # 6 = Health Post (deepest level)
MOH_ORG_UNITS_MAX_LEVEL = 6  # 6 = Health Post (deepest level)

# ---------------------------------------------------------------------------
# Brand-asset blueprint — serves the MoH logo (and any future brand assets)
# from a webpack-safe directory so they survive `npm run build`.
# ---------------------------------------------------------------------------
from superset.moh_assets import moh_assets_bp as _moh_assets_bp  # noqa: E402

BLUEPRINTS = [_ai_chat_bp, _moh_orgunits_bp, _moh_assets_bp]
BLUEPRINTS = [
    _ai_chat_bp,
    _moh_orgunits_bp,
    _moh_assets_bp,
    _hpc_bp,
]

MAPBOX_STYLES = [
    {
        "id": "blank",
        "label": "Blank",
        "url": "",
    },
]
