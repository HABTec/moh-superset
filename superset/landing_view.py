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
from typing import Any

from flask import redirect
from flask_appbuilder import expose, IndexView
from flask_login import current_user

_TAB_SUBTITLES: dict[str, tuple[str, str]] = {
    "summary":       ("Top key performance indicators", "summary"),
    "data quality":  ("Report completeness & timeliness", "quality"),
    "monthly":       ("Monthly reported indicators", "monthly"),
    "quarterly":     ("Quarterly reported indicators", "quarterly"),
    "multi-source":  ("Different data sources", "multi-source"),
    "multi source":  ("Different data sources", "multi-source"),
    "triangulation": ("Different data sources", "multi-source"),
    "annual":        ("Annual reported indicators", "quarterly"),
    "yearly":        ("Yearly reported indicators", "quarterly"),
}

# Optional display-name overrides — when the dashboard tab is named X but the
# landing tile should read Y. Key is the lowercased substring matched in the
# tab title; value is the replacement title shown in the tile heading AND
# the "View ..." link. Lets users keep their existing tab names in the
# dashboard while presenting friendlier wording on the landing.
_TAB_TITLE_OVERRIDES: dict[str, str] = {
    "triangulation": "Multi-Source Analytics",
}


def _tab_decor(title: str | None) -> dict[str, str]:
    t = (title or "").lower()
    for key, (subtitle, icon) in _TAB_SUBTITLES.items():
        if key in t:
            return {"subtitle": subtitle, "icon": icon}
    return {"subtitle": "", "icon": "default"}


def _override_title(title: str | None) -> str | None:
    """Apply _TAB_TITLE_OVERRIDES to the tab title (case-insensitive substring)."""
    if not title:
        return title
    t = title.lower()
    for key, replacement in _TAB_TITLE_OVERRIDES.items():
        if key in t:
            return replacement
    return title


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
                "title": d.dashboard_title,
                "url": d.url,
                "description": (d.description or "").strip(),
                "tabs": tabs,
            })

        featured = max(
            (d for d in dashboards if d["tabs"]),
            key=lambda d: len(d["tabs"]),
            default=None,
        )
        others = [d for d in dashboards if d is not featured]
        return self.render_template(
            self.index_template,
            featured=featured,
            others=others,
        )
