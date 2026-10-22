# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""MoH dashboard tabs reserved for level-one (national) users.

``MOH_RESTRICTED_TABS`` maps a dashboard id to the titles of its tabs that only
level-one users may see, each with the org units whose users may see it too:

    MOH_RESTRICTED_TABS = {
        3: {"Multi Source": [], "Triangulation": ["G9hDiPNoB7d"]},
    }

A user may also see a tab when their assigned org unit is one of those units or
lies below one (e.g. a Dire Dawa woreda or facility for Dire Dawa City
Administration). For everyone else the tab, with everything inside it, is left
out of the dashboard's layout, chart list and tab list, and its charts' data is
refused on that dashboard.

Admins, owners of the dashboard and level-one users see every tab. Owners are
exempt so that saving the dashboard in edit mode never drops tabs they could
not see.
"""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from flask import current_app, g

from superset.utils import json

if TYPE_CHECKING:
    from superset.models.dashboard import Dashboard

logger = logging.getLogger(__name__)

# Dire Dawa City Administration, whose users also see the Triangulation tab.
DIRE_DAWA_ORG_UNIT_ID = "G9hDiPNoB7d"

DEFAULT_MOH_RESTRICTED_TABS: dict[int, dict[str, list[str]]] = {
    3: {
        "Multi Source": [],
        "Triangulation": [DIRE_DAWA_ORG_UNIT_ID],
    },
}


def _normalize(title: str) -> str:
    return " ".join(str(title).split()).casefold()


def _restricted_tabs(dashboard_id: int) -> dict[str, list[str]]:
    """Restricted tab titles (normalized) of a dashboard, with their extra units."""
    configured = current_app.config.get(
        "MOH_RESTRICTED_TABS", DEFAULT_MOH_RESTRICTED_TABS
    )
    try:
        rules = {int(key): value for key, value in (configured or {}).items()}
    except (TypeError, ValueError, AttributeError):
        logger.error("MOH_RESTRICTED_TABS is invalid; no tab is restricted")
        return {}
    return {
        _normalize(title): [str(unit) for unit in units or []]
        for title, units in (rules.get(dashboard_id) or {}).items()
    }


def _sees_all_tabs(dashboard: Dashboard) -> bool:
    # pylint: disable=import-outside-toplevel
    from superset import security_manager

    if security_manager.is_admin() or security_manager.is_owner(dashboard):
        return True
    is_level_one = getattr(
        security_manager, "user_can_access_level_one_dashboard", None
    )
    return bool(callable(is_level_one) and is_level_one())


def _user_org_unit_path() -> str:
    """The DHIS2 path of the user's assigned org unit; empty when unknown."""
    # pylint: disable=import-outside-toplevel
    from superset.moh_orgunits_api import _assigned_unit

    try:
        unit = _assigned_unit()
    except Exception:  # pylint: disable=broad-except
        logger.exception("Unable to look up the user's org unit for tab access")
        return ""
    return str((unit or {}).get("path") or "")


def _in_org_units(path: str, org_unit_ids: list[str]) -> bool:
    parts = path.strip("/").split("/")
    return any(unit in parts for unit in org_unit_ids)


def _layout(dashboard: Dashboard) -> dict[str, Any]:
    try:
        layout = json.loads(dashboard.position_json or "{}")
    except (TypeError, ValueError):
        return {}
    return layout if isinstance(layout, dict) else {}


def _components(layout: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {key: comp for key, comp in layout.items() if isinstance(comp, dict)}


def hidden_tab_ids(dashboard: Dashboard) -> set[str]:
    """Layout ids of the tabs the current user may not see on ``dashboard``."""
    rules = _restricted_tabs(int(dashboard.id))
    if not rules:
        return set()

    memo: dict[int, set[str]] = g.setdefault("moh_hidden_tab_ids", {})
    if dashboard.id in memo:
        return memo[dashboard.id]

    hidden: set[str] = set()
    if not _sees_all_tabs(dashboard):
        user_path: str | None = None
        for key, comp in _components(_layout(dashboard)).items():
            if comp.get("type") != "TAB":
                continue
            title = _normalize((comp.get("meta") or {}).get("text") or "")
            if title not in rules:
                continue
            if user_path is None:
                user_path = _user_org_unit_path()
            if not _in_org_units(user_path, rules[title]):
                hidden.add(key)
    memo[dashboard.id] = hidden
    return hidden


def remove_tabs(
    layout: dict[str, Any], tab_ids: set[str]
) -> tuple[dict[str, Any], set[int]]:
    """
    Removes tabs, and everything inside them, from a dashboard layout.

    :param layout: the dashboard's position data
    :param tab_ids: layout ids of the tabs to remove
    :return: the remaining layout, and the ids of charts it no longer shows
    """
    components = _components(layout)
    removed: set[str] = set()
    pending = [tab_id for tab_id in tab_ids if tab_id in components]
    while pending:
        key = pending.pop()
        if key in removed:
            continue
        removed.add(key)
        pending.extend(
            child
            for child in components.get(key, {}).get("children") or []
            if child in components
        )

    def chart_ids(keys: Any) -> set[int]:
        ids: set[int] = set()
        for key in keys:
            comp = components[key]
            chart_id = (comp.get("meta") or {}).get("chartId")
            if comp.get("type") == "CHART" and chart_id is not None:
                ids.add(int(chart_id))
        return ids

    kept_keys = set(components) - removed
    hidden_charts = chart_ids(removed) - chart_ids(kept_keys)

    remaining: dict[str, Any] = {}
    for key, value in layout.items():
        if key in removed:
            continue
        if isinstance(value, dict) and value.get("children"):
            value = {
                **value,
                "children": [c for c in value["children"] if c not in removed],
            }
        remaining[key] = value
    return remaining, hidden_charts


def hidden_chart_ids(dashboard: Dashboard) -> set[int]:
    """Ids of charts that only appear in tabs hidden from the current user."""
    hidden_tabs = hidden_tab_ids(dashboard)
    if not hidden_tabs:
        return set()
    return remove_tabs(_layout(dashboard), hidden_tabs)[1]


def restrict_dashboard_result(
    dashboard: Dashboard, result: dict[str, Any]
) -> dict[str, Any]:
    """Drops hidden tabs from a serialized dashboard's layout."""
    hidden_tabs = hidden_tab_ids(dashboard)
    if not hidden_tabs or not result.get("position_json"):
        return result
    layout, _ = remove_tabs(_layout(dashboard), hidden_tabs)
    return {**result, "position_json": json.dumps(layout)}


def restrict_tabs_result(
    dashboard: Dashboard, result: dict[str, Any]
) -> dict[str, Any]:
    """Drops hidden tabs from a dashboard's tab list and tab tree."""
    hidden_tabs = hidden_tab_ids(dashboard)
    if not hidden_tabs:
        return result

    def prune(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {**node, "children": prune(node.get("children") or [])}
            for node in nodes
            if node.get("value", node.get("id")) not in hidden_tabs
        ]

    return {
        **result,
        "all_tabs": {
            key: title
            for key, title in (result.get("all_tabs") or {}).items()
            if key not in hidden_tabs
        },
        "tab_tree": prune(result.get("tab_tree") or []),
    }
