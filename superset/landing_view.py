# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
"""MoH branded landing page replacing the default index redirect."""

from __future__ import annotations

import json
import re
from typing import Any

from flask import current_app, redirect
from flask_appbuilder import expose, IndexView
from flask_login import current_user

_TAB_SUBTITLES: dict[str, tuple[str, str]] = {
    "summary":       ("Top key performance indicators", "summary"),
    "data quality":  ("Report completeness & timeliness", "quality"),
    "monthly":       ("Monthly reported indicators", "monthly"),
    "quarterly":     ("Quarterly reported indicators", "quarterly"),
    # NOTE: "triangulation" matches BEFORE "multi source" — order matters because
    # `_tab_decor` returns on first substring match. Keep triangulation above
    # multi-source so dashboards with both tabs get distinct icons.
    "triangulation": ("Cross-source comparison", "triangulation"),
    "multi-source":  ("Different data sources", "multi-source"),
    "multi source":  ("Different data sources", "multi-source"),
    "annual":        ("Annual reported indicators", "quarterly"),
    "yearly":        ("Yearly reported indicators", "quarterly"),
    "meskot":        ("Explore data quality assurance", "quality"),
}

# Optional display-name overrides — when the dashboard tab is named X but the
# landing tile should read Y. Key is the lowercased substring matched in the
# tab title; value is the replacement title shown in the tile heading AND
# the "View ..." link. Lets users keep their existing tab names in the
# dashboard while presenting friendlier wording on the landing.
# Empty by default — add entries here if you want to rename specific tabs
# on the landing without touching the dashboard config.
_TAB_TITLE_OVERRIDES: dict[str, str] = {
    "monitering": "Monitoring",
}


def _tab_decor(title: str | None) -> dict[str, str]:
    t = (title or "").lower()
    for key, (subtitle, icon) in _TAB_SUBTITLES.items():
        if key in t:
            return {"subtitle": subtitle, "icon": icon}
    return {"subtitle": "", "icon": "default"}


def _override_title(title: str | None) -> str | None:
    """Apply _TAB_TITLE_OVERRIDES via case-insensitive substring replacement."""
    if not title:
        return title
    result = title
    for key, replacement in _TAB_TITLE_OVERRIDES.items():
        result = re.sub(re.escape(key), replacement, result, flags=re.IGNORECASE)
    return result


def _extract_tabs(position_json_str: str | None) -> list[dict[str, Any]]:
    """Return [{id, title, subtitle, icon}] for TOP-LEVEL tabs only."""
    if not position_json_str:
        return []
    try:
        position = json.loads(position_json_str)
    except (ValueError, TypeError):
        return []
    if not isinstance(position, dict):
        return []

    top_tab_ids: list[str] = []
    for component in position.values():
        if not isinstance(component, dict) or component.get("type") != "TABS":
            continue
        parents = component.get("parents") or []
        # Skip nested TABS — only the outermost tab strip becomes tiles.
        if any(str(p).startswith(("TAB-", "TABS-")) for p in parents):
            continue
        top_tab_ids = component.get("children") or []
        break

    out: list[dict[str, Any]] = []
    for tab_id in top_tab_ids:
        comp = position.get(tab_id)
        if not isinstance(comp, dict) or comp.get("type") != "TAB":
            continue
        meta = comp.get("meta") or {}
        raw_title = meta.get("text") or meta.get("defaultText") or tab_id
        # Decor (subtitle + icon) keys off the ORIGINAL tab title so a rename
        # via _TAB_TITLE_OVERRIDES doesn't break the matching.
        if "meskot" in raw_title.lower():
            continue
        decor = _tab_decor(raw_title)
        # Display title shown to users — overridable via _TAB_TITLE_OVERRIDES.
        title = _override_title(raw_title) or raw_title
        entry: dict[str, Any] = {"id": tab_id, "title": title}
        entry.update(decor)
        out.append(entry)
    return out


class MoHLandingView(IndexView):
    """Branded landing page replacing FAB's default index.

    Lists published dashboards as tiles, picking the dashboard with the most
    top-level tabs as the "featured" hero, and showing the rest as compact
    pills below.
    """

    index_template = "superset/landing.html"

    @expose("/")
    def index(self):  # type: ignore[override]
        if not current_user.is_authenticated:
            return redirect("/login/?next=/")

        # Local imports — top-level imports here would create a cycle since
        # this module is loaded during app initialization.
        from superset import db
        from superset.extensions import security_manager
        from superset.models.dashboard import Dashboard

        rows = (
            db.session.query(Dashboard)
            .order_by(Dashboard.dashboard_title)
            .all()
        )
        dashboards: list[dict[str, Any]] = []
        for d in rows:
            tabs = _extract_tabs(d.position_json)
            dashboards.append({
                "id": d.id,
                "slug": d.slug,
                "title": _override_title(d.dashboard_title) or d.dashboard_title,
                "url": d.url,
                "description": (d.description or "").strip(),
                "tabs": tabs,
            })

        # Pin a specific hero dashboard when MOH_FEATURED_DASHBOARD is set
        # (matches by numeric id or slug); otherwise fall back to promoting
        # whichever dashboard has the most top-level tabs.
        featured = None
        featured_cfg = current_app.config.get("MOH_FEATURED_DASHBOARD")
        if featured_cfg is not None:
            cfg = str(featured_cfg)
            featured = next(
                (d for d in dashboards if str(d["id"]) == cfg or d["slug"] == cfg),
                None,
            )
        if featured is None:
            featured = max(
                (d for d in dashboards if d["tabs"]),
                key=lambda d: len(d["tabs"]),
                default=None,
            )
        others = [d for d in dashboards if d is not featured]

        # Only MoHSecurityManager exposes this helper. If the server config
        # forgot CUSTOM_SECURITY_MANAGER, fall back to always showing the link
        # instead of AttributeError → 500 on "/".
        health_intelligence_url = current_app.config.get(
            "MOH_HEALTH_INTELLIGENCE_URL"
        )
        can_access_moh_dashboard = getattr(
            security_manager, "can_access_moh_dashboard", None
        )
        if callable(can_access_moh_dashboard):
            restricted_dashboard = next(
                (dashboard for dashboard in rows if dashboard.id == 8),
                None,
            )
            if not can_access_moh_dashboard(restricted_dashboard):
                health_intelligence_url = None

        return self.render_template(
            self.index_template,
            featured=featured,
            others=others,
            is_admin=security_manager.is_admin(),
            health_intelligence_url=health_intelligence_url,
        )
