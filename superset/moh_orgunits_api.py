# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.
"""
DHIS2-shaped API adapter for the MoH organisation-unit hierarchy.

Exposes a small set of read-only JSON endpoints under `/api/v1/moh/dhis2/...`
whose response shape matches what the `@dhis2/ui` OrganisationUnitTree
component expects when wrapped in a DataProvider configured with::

    baseUrl: "/api/v1/moh/dhis2"

The endpoints read directly from the `org_units` table on the registered
Superset ClickHouse connection (default name: "MOH_Click_Hhouse"). No new
tables and no schema changes are required.

Endpoints
---------
GET /api/v1/moh/dhis2/organisationUnits?level=<N>
    List all org units at level N (default: configured root level, i.e. 2 =
    Region). Used by the tree component to fetch the initial root nodes.

GET /api/v1/moh/dhis2/organisationUnits/<uid>
    Return one org unit + its DIRECT children. Used by the tree component to
    lazy-load when a node is expanded.

Both endpoints are gated on a logged-in Superset session. The React component
runs in the browser so the same-origin session cookie satisfies auth
automatically.

Registered with Flask via the BLUEPRINTS list in `superset/moh_branding.py` —
no edits to upstream Superset init code.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, abort, current_app, jsonify, request
from flask_login import current_user
from sqlalchemy import text

logger = logging.getLogger(__name__)

moh_orgunits_bp = Blueprint(
    "moh_orgunits_dhis2",
    __name__,
    url_prefix="/api/v1/moh/dhis2",
)


# ---------------------------------------------------------------------------
# Config helpers — every knob is overridable via Flask config so a single
# code path works in Docker dev, native Ubuntu, and any future deployment.
# Defaults match the MoH ClickHouse setup as currently registered in Superset.
# ---------------------------------------------------------------------------

def _db_name() -> str:
    return current_app.config.get("MOH_ORG_UNITS_DB_NAME", "MOH_Click_Hhouse")


def _schema() -> str:
    return current_app.config.get("MOH_ORG_UNITS_SCHEMA", "moh")


def _table() -> str:
    return current_app.config.get("MOH_ORG_UNITS_TABLE", "org_units")


def _root_level() -> int:
    return int(current_app.config.get("MOH_ORG_UNITS_ROOT_LEVEL", 2))


def _max_level() -> int:
    """Deepest org unit level. 6 covers region→zone→woreda→phcu→health_post."""
    return int(current_app.config.get("MOH_ORG_UNITS_MAX_LEVEL", 6))


def _qualified_table() -> str:
    """`"schema"."table"` for ClickHouse — quoted to be safe with reserved words."""
    schema = _schema()
    return f'"{schema}"."{_table()}"' if schema else f'"{_table()}"'


def _get_database():
    """Look up the registered Superset Database row for our ClickHouse connection."""
    # Lazy imports — Superset's db extension isn't ready at config-load time.
    from superset import db as superset_db
    from superset.models.core import Database

    name = _db_name()
    database = (
        superset_db.session.query(Database).filter_by(database_name=name).first()
    )
    if database is None:
        logger.error("Database connection %r is not registered in Superset", name)
        abort(503, f"Database '{name}' is not configured. Add it in Superset → "
                   f"Settings → Database Connections, or set MOH_ORG_UNITS_DB_NAME "
                   f"to an existing connection name.")
    return database


# ---------------------------------------------------------------------------
# Row → DHIS2 JSON mapping
# ---------------------------------------------------------------------------

_LEVEL_ID_COLS = ("level2id", "level3id", "level4id", "level5id", "level6id")


def _row_to_dhis2(row, has_children: bool | None = None) -> dict[str, Any]:
    """Translate one org_units row into a DHIS2-shaped dict.

    `has_children` is informational. If unknown, omit it; the tree component
    falls back to attempting an expansion request.
    """
    m = row._mapping
    # path = /level2id/level3id/.../self.id — order matches DHIS2's "/" path
    path_parts = [m[col] for col in _LEVEL_ID_COLS if m.get(col)]
    if not path_parts or path_parts[-1] != m["id"]:
        path_parts.append(m["id"])

    out: dict[str, Any] = {
        "id": m["id"],
        "displayName": m["name"],
        "level": m["level"],
        "path": "/" + "/".join(path_parts),
        # Stubbed access/publicAccess keep @dhis2/ui happy without RBAC plumbing.
        "access": {
            "read": True,
            "update": False,
            "delete": False,
            "externalize": False,
            "manage": False,
            "write": False,
        },
        "publicAccess": "r-------",
    }
    if has_children is not None:
        out["children"] = [] if not has_children else out.get("children", [])
    return out


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

def _require_authenticated() -> None:
    """Manual auth check.

    We do NOT use flask_login's @login_required because under Superset's
    /api/v1/* namespace it triggers a redirect to url_for('login'), but
    Superset's actual login endpoint is registered as 'AuthDBView.login' —
    Flask-Login can't build the URL and the request fails with a generic
    backend error instead of the expected 401.
    """
    if not getattr(current_user, "is_authenticated", False):
        abort(401)


@moh_orgunits_bp.route("/organisationUnits", methods=["GET"])
def list_units():
    """List all org units at a given level (no children inlined).

    Used by the tree component for its initial root fetch.

    Query params
    ------------
    level : int, optional
        Level to return. Defaults to MOH_ORG_UNITS_ROOT_LEVEL (2 = Region).
    """
    _require_authenticated()
    level = request.args.get("level", type=int) or _root_level()
    if level < 1 or level > _max_level():
        abort(400, f"level must be between 1 and {_max_level()}")

    database = _get_database()
    cols = ", ".join(_LEVEL_ID_COLS)
    # get_sqla_engine() is a @contextmanager (handles SSH tunnels, OAuth2, etc.)
    with database.get_sqla_engine() as engine:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT id, name, level, {cols} "
                    f"FROM {_qualified_table()} "
                    f"WHERE level = :lvl "
                    f"ORDER BY name"
                ),
                {"lvl": level},
            ).all()
    return jsonify({
        "organisationUnits": [_row_to_dhis2(r) for r in rows],
    })


@moh_orgunits_bp.route("/organisationUnits/<uid>", methods=["GET"])
def get_unit(uid: str):
    """Return one org unit + its DIRECT children (lazy-load on expand)."""
    _require_authenticated()
    database = _get_database()
    cols = ", ".join(_LEVEL_ID_COLS)

    with database.get_sqla_engine() as engine:
        with engine.connect() as conn:
            unit = conn.execute(
                text(
                    f"SELECT id, name, level, {cols} "
                    f"FROM {_qualified_table()} "
                    f"WHERE id = :uid LIMIT 1"
                ),
                {"uid": uid},
            ).first()
            if unit is None:
                abort(404, f"Org unit '{uid}' not found")

            parent_level = unit._mapping["level"]
            children = []
            if parent_level < _max_level():
                # Children have level = parent_level + 1, and their `level{parent}id`
                # column points back to this parent's id.
                parent_col = f"level{parent_level}id"
                if parent_col in _LEVEL_ID_COLS:
                    children = conn.execute(
                        text(
                            f"SELECT id, name, level, {cols} "
                            f"FROM {_qualified_table()} "
                            f"WHERE level = :child_lvl "
                            f"  AND {parent_col} = :parent_id "
                            f"ORDER BY name"
                        ),
                        {"child_lvl": parent_level + 1, "parent_id": uid},
                    ).all()

    response = _row_to_dhis2(unit)
    response["children"] = [_row_to_dhis2(r) for r in children]
    return jsonify(response)


# ---------------------------------------------------------------------------
# Visual test page — temporary. Renders the live org_units tree against the
# JSON endpoints above using plain JS (no React, no @dhis2/ui). Lets us prove
# the API contract works end-to-end before integrating @dhis2/ui into a real
# Superset Native Filter plugin in the frontend bundle.
#
# Open in your browser: /api/v1/moh/dhis2/test
# ---------------------------------------------------------------------------

_TEST_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>MoH Org Unit Tree — API smoke test</title>
<style>
  body { font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
         max-width: 880px; margin: 32px auto; padding: 0 16px;
         color: #0a2540; background: #fff; }
  h1 { font-size: 1.4rem; margin: 0 0 8px; }
  p.sub { color: #6b7c93; margin: 0 0 20px; font-size: 0.9rem; }
  ul.tree { list-style: none; padding-left: 0; }
  ul.tree ul { list-style: none; padding-left: 22px; border-left: 1px dotted #d6e3ff;
               margin: 4px 0 4px 8px; }
  li { padding: 3px 0; }
  .row { display: flex; align-items: center; gap: 8px; cursor: pointer;
         padding: 4px 8px; border-radius: 6px; user-select: none; }
  .row:hover { background: #eef4ff; }
  .row.selected { background: #1a5cff; color: #fff; }
  .row.selected .level { color: rgba(255,255,255,0.8); }
  .caret { width: 14px; display: inline-block; color: #6b7c93; font-size: 0.8rem; }
  .caret.leaf { color: #d6e3ff; }
  .level { color: #6b7c93; font-size: 0.78rem; }
  .selection { background: #f7faff; border: 1px solid #d6e3ff; border-radius: 10px;
               padding: 14px 18px; margin: 18px 0; font-size: 0.92rem; }
  .selection code { background: #eef4ff; padding: 1px 6px; border-radius: 4px; }
  .err { color: #c53030; background: #fff5f5; border: 1px solid #fed7d7;
         padding: 8px 12px; border-radius: 6px; }
</style>
</head>
<body>

<h1>MoH Org Unit Tree — API smoke test</h1>
<p class="sub">Reads from <code>/api/v1/moh/dhis2/organisationUnits</code>. Click a node to select; click the caret to expand/collapse. Selection is logged below.</p>

<div class="selection" id="selection">
  <strong>Selected:</strong> <span id="selected-name">(none)</span> &middot;
  <code id="selected-id">—</code> &middot;
  level <span id="selected-level">—</span>
</div>

<ul class="tree" id="root"></ul>

<!-- JS served as external file (script src=...) to avoid CSP inline-script blocks -->
<script src="/api/v1/moh/dhis2/test.js"></script>

</body>
</html>
"""


_TEST_PAGE_JS = """
const ROOT_LEVEL = 1;
const API = '/api/v1/moh/dhis2/organisationUnits';

async function fetchChildren(uid) {
  const r = await fetch(API + '/' + uid, { credentials: 'same-origin' });
  if (!r.ok) throw new Error('HTTP ' + r.status + ' fetching ' + uid);
  const data = await r.json();
  return data.children || [];
}

async function fetchRoots() {
  const r = await fetch(API + '?level=' + ROOT_LEVEL, { credentials: 'same-origin' });
  if (!r.ok) throw new Error('HTTP ' + r.status + ' fetching roots');
  const data = await r.json();
  return data.organisationUnits || [];
}

function renderNode(unit, parentUl) {
  const li = document.createElement('li');
  const row = document.createElement('div');
  row.className = 'row';
  row.dataset.id = unit.id;
  row.dataset.level = unit.level;
  row.dataset.name = unit.displayName;

  const caret = document.createElement('span');
  caret.className = 'caret';
  caret.textContent = unit.level < 6 ? '\\u25B8' : '\\u00B7';
  if (unit.level >= 6) caret.classList.add('leaf');
  row.appendChild(caret);

  const label = document.createElement('span');
  label.textContent = (unit.displayName || '').trim();
  row.appendChild(label);

  const lvl = document.createElement('span');
  lvl.className = 'level';
  lvl.textContent = '\\u00B7 L' + unit.level;
  row.appendChild(lvl);

  let childUl = null;
  let expanded = false;

  caret.addEventListener('click', async (e) => {
    e.stopPropagation();
    if (unit.level >= 6) return;
    if (expanded) {
      childUl.style.display = 'none';
      caret.textContent = '\\u25B8';
      expanded = false;
      return;
    }
    if (!childUl) {
      childUl = document.createElement('ul');
      try {
        const children = await fetchChildren(unit.id);
        if (children.length === 0) {
          caret.classList.add('leaf');
          caret.textContent = '\\u00B7';
          return;
        }
        children.forEach(c => renderNode(c, childUl));
      } catch (err) {
        const ee = document.createElement('li');
        ee.className = 'err';
        ee.textContent = err.message;
        childUl.appendChild(ee);
      }
      li.appendChild(childUl);
    }
    childUl.style.display = '';
    caret.textContent = '\\u25BE';
    expanded = true;
  });

  row.addEventListener('click', () => {
    document.querySelectorAll('.row.selected').forEach(r => r.classList.remove('selected'));
    row.classList.add('selected');
    document.getElementById('selected-name').textContent = (unit.displayName || '').trim();
    document.getElementById('selected-id').textContent = unit.id;
    document.getElementById('selected-level').textContent = unit.level;
  });

  li.appendChild(row);
  parentUl.appendChild(li);
}

(async () => {
  const rootUl = document.getElementById('root');
  try {
    const roots = await fetchRoots();
    roots.forEach(r => renderNode(r, rootUl));
  } catch (err) {
    rootUl.innerHTML = '<li class="err">' + err.message + '</li>';
  }
})();
"""


@moh_orgunits_bp.route("/test", methods=["GET"])
def test_page():
    """Smoke-test page — vanilla JS tree against the DHIS2-shape endpoints.

    Same origin as Superset so the session cookie flows through naturally.
    JS is served as a separate file (route below) so we don't trip CSP's
    inline-script policy.
    """
    _require_authenticated()
    return _TEST_PAGE_HTML, 200, {"Content-Type": "text/html; charset=utf-8"}


@moh_orgunits_bp.route("/test.js", methods=["GET"])
def test_page_js():
    """Companion JS for the smoke-test page. External script = CSP-safe."""
    _require_authenticated()
    return _TEST_PAGE_JS, 200, {"Content-Type": "application/javascript; charset=utf-8"}
