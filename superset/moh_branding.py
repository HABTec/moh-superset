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
# FAVICONS = [{"href": "/static/assets/images/logomohnewww.png"}]

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
}

# ---------------------------------------------------------------------------
# MCP server (dev mode)
# ---------------------------------------------------------------------------
MCP_AUTH_ENABLED = False
MCP_DEV_USERNAME = "admin"

# Public-facing base URL the MCP server uses when generating explore / SQL Lab
# / dashboard links it returns to the LLM. The upstream docker dev config
# (docker/pythonpath_dev/superset_config.py) hardcodes localhost:8888, which is
# unreachable from the user's browser when SUPERSET_PORT is overridden.
# Override here so the AI Assistant returns clickable links.
import os as _os  # noqa: E402

WEBDRIVER_BASEURL_USER_FRIENDLY = _os.environ.get(
    "MOH_PUBLIC_URL", "http://localhost:8090/"
)
# MCP_SERVICE_URL is the *MCP server's own* base URL (used for screenshots,
# not explore links). Kept for screenshot tools.
MCP_SERVICE_URL = _os.environ.get("MCP_SERVICE_URL", "http://localhost:8090")

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
from superset.moh_orgunits_api import moh_orgunits_bp as _moh_orgunits_bp  # noqa: E402

MOH_ORG_UNITS_DB_NAME = "MOH_Click_Hhouse"
MOH_ORG_UNITS_SCHEMA = "moh"
MOH_ORG_UNITS_TABLE = "org_units"
MOH_ORG_UNITS_ROOT_LEVEL = 2  # 2 = Region (start tree at the 14 Ethiopian regions)
MOH_ORG_UNITS_MAX_LEVEL = 6   # 6 = Health Post (deepest level)

# ---------------------------------------------------------------------------
# Brand-asset blueprint — serves the MoH logo (and any future brand assets)
# from a webpack-safe directory so they survive `npm run build`.
# ---------------------------------------------------------------------------
from superset.moh_assets import moh_assets_bp as _moh_assets_bp  # noqa: E402

BLUEPRINTS = [_ai_chat_bp, _moh_orgunits_bp, _moh_assets_bp]

# Landing page is wired in Python — see superset/views/landing.py and the
# one-line swap in superset/initialization/__init__.py (configure_fab).
