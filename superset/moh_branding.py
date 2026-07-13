# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.
"""
DEPRECATED — use superset_config.py at the project root instead.

All MoH configuration (branding, BLUEPRINTS, HIS/PHC iframe URLs, Redis,
Celery, feature flags) lives in a single file:

    cp superset_config.example.py superset_config.py
    export SUPERSET_CONFIG_PATH=/abs/path/to/moh-superset/superset_config.py

This module remains only so older imports do not crash. It re-exports branding
constants for backward compatibility but does NOT register Flask blueprints.
"""

from superset.config import (
    THEME_DARK as _APACHE_THEME_DARK,
    THEME_DEFAULT as _APACHE_THEME_DEFAULT,
)

VERSION_STRING = "MoH 6.0"
APP_NAME = "MoH Analytics Portal"
APP_ICON = "/moh-static/logomohnewww.png"
APP_ICON_WIDTH = 150
LOGO_TARGET_PATH = "/"
LOGO_TOOLTIP = "MoH Analytics Portal"
LOGO_RIGHT_TEXT = ""
FAVICONS = [{"href": "/moh-static/moh_icon.png"}]

_MOH_BRAND_TOKENS = {
    "brandLogoUrl": APP_ICON,
    "brandLogoAlt": "Ministry of Health",
    "brandAppName": APP_NAME,
    "brandLogoHref": "/",
    "brandLogoHeight": "32px",
    "brandSpinnerUrl": "/moh-static/moh_icon.png",
    "colorPrimary": "#1a5cff",
    "colorLink": "#1a5cff",
}

THEME_DEFAULT = {
    **_APACHE_THEME_DEFAULT,
    "token": {**_APACHE_THEME_DEFAULT["token"], **_MOH_BRAND_TOKENS},
}

THEME_DARK = (
    {
        **_APACHE_THEME_DARK,
        "token": {**_APACHE_THEME_DARK["token"], **_MOH_BRAND_TOKENS},
    }
    if _APACHE_THEME_DARK
    else None
)

# Blueprints are registered only via superset_config.py BLUEPRINTS.
BLUEPRINTS: list = []
