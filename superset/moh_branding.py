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
APP_ICON = "/static/assets/images/logomohnewww.png"
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

# Landing page is wired in Python — see superset/views/landing.py and the
# one-line swap in superset/initialization/__init__.py (configure_fab).
