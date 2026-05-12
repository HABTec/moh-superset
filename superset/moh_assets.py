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

import os

from flask import Blueprint, abort, send_from_directory

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
    # add more brand asset filenames here when needed
}


@moh_assets_bp.route("/<filename>")
def serve_asset(filename: str):
    """Serve a whitelisted brand asset from the webpack-safe location."""
    if filename not in _ALLOWED_FILES:
        abort(404)
    return send_from_directory(_BRAND_ASSET_DIR, filename)
