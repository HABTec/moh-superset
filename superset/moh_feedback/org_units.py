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
"""Look up the org units a portal user belongs to."""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from flask import current_app, Flask
from sqlalchemy import bindparam, text

from superset.moh_alerts.connection import get_moh_database

logger = logging.getLogger(__name__)

LEVELS = range(1, 8)
TOP_LEVEL = 1
DEFAULT_LOOKUP_TIMEOUT_SECONDS = 5
# A separate pool, so a stalled ClickHouse cannot hold up the web request
_LOOKUP_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="moh-feedback")


class OrgUnitLookupError(Exception):
    """ClickHouse could not answer an org-unit question in time."""


@dataclass(frozen=True)
class OrgUnit:
    """One org unit and its position in the tree."""

    id: str
    name: str
    path: str
    # level1id to level7id; a position is None below the unit's own level
    level_ids: tuple[str | None, ...]
    closed: bool
    level: int = 0
    leaf: bool = False

    @property
    def ancestor_ids(self) -> tuple[str, ...]:
        """The units above this one, nearest first."""
        chain = [unit_id for unit_id in self.level_ids if unit_id]
        if self.id in chain:
            chain = chain[: chain.index(self.id)]
        return tuple(reversed(chain))


def _optional_text(value: Any) -> str | None:
    """Return text, or None for the NULL or empty values used for "no value"."""
    text_value = str(value).strip() if value is not None else ""
    return text_value or None


def org_unit_from_row(row: Mapping[str, Any]) -> OrgUnit:
    """Build an ``OrgUnit`` from a row of the org-unit table."""
    names = [_optional_text(row.get(f"l{level}name")) for level in LEVELS]
    own_name = _optional_text(row.get("name")) or str(row["id"])
    return OrgUnit(
        id=str(row["id"]),
        name=own_name,
        path=" › ".join(name for name in names if name) or own_name,
        level_ids=tuple(_optional_text(row.get(f"level{level}id")) for level in LEVELS),
        closed=bool(row.get("is_closed")),
        level=int(row.get("level") or 0),
        leaf=bool(row.get("leaf")),
    )


def selectable_units(units: list[OrgUnit]) -> list[OrgUnit]:
    """Offer a user's open units, or their closed units if they have no open one."""
    return [unit for unit in units if not unit.closed] or units


def _organisation_database() -> Any:
    # pylint: disable=import-outside-toplevel
    from superset.extensions import db
    from superset.models.core import Database

    name = current_app.config.get("MOH_ORG_UNITS_DB_NAME", "MOH_Click_Hhouse")
    database = db.session.query(Database).filter_by(database_name=name).one_or_none()
    return get_moh_database(database.id if database else None)


def _table(schema: str, table: str) -> str:
    return f"`{schema}`.`{table}`"


def _units_table() -> str:
    config = current_app.config
    return _table(
        config.get("MOH_ORG_UNITS_SCHEMA", "moh"),
        config.get("MOH_ORG_UNITS_TABLE", "org_units"),
    )


def _mapping_table() -> str:
    config = current_app.config
    return _table(
        config.get(
            "MOH_USER_ORG_UNITS_SCHEMA", config.get("MOH_ORG_UNITS_SCHEMA", "moh")
        ),
        config.get("MOH_USER_ORG_UNITS_TABLE", "dim_user_orgunit"),
    )


def _units_select(condition: str, suffix: str = "") -> str:
    """Select org units, with FINAL because ClickHouse may hold duplicate rows."""
    level_columns = ", ".join(
        f"o.level{level}id AS level{level}id, o.l{level}name AS l{level}name"
        for level in LEVELS
    )
    return (
        "SELECT toString(o.id) AS id, o.name AS name, o.level AS level, "  # noqa: S608 - config-quoted identifiers
        "o.leaf AS leaf, "
        "(o.closeddate IS NOT NULL AND o.closeddate <= now()) AS is_closed, "
        f"{level_columns} FROM {_units_table()} AS o FINAL "
        f"WHERE {condition} {suffix}"
    )


def _fetch_rows(
    app: Flask, database: Any, query: Any, parameters: dict[str, Any]
) -> list[dict[str, Any]]:
    """Run one ClickHouse query. Runs on a lookup thread."""
    with app.app_context():
        with database.get_sqla_engine() as engine:
            with engine.connect() as connection:
                rows = connection.execute(query, parameters).mappings()
                return [dict(row) for row in rows]


def _query(query: Any, parameters: dict[str, Any]) -> list[dict[str, Any]]:
    """Run a query, raising ``OrgUnitLookupError`` if it fails or is too slow."""
    limit = current_app.config.get(
        "MOH_FEEDBACK_ORG_LOOKUP_TIMEOUT", DEFAULT_LOOKUP_TIMEOUT_SECONDS
    )
    future: Future[list[dict[str, Any]]] | None = None
    try:
        future = _LOOKUP_POOL.submit(
            _fetch_rows,
            current_app._get_current_object(),  # pylint: disable=protected-access
            _organisation_database(),
            query,
            parameters,
        )
        return future.result(timeout=limit)
    except Exception as ex:
        if future is not None:
            future.cancel()
        raise OrgUnitLookupError(str(ex)) from ex


def unit_ids_for_username(
    rows: Iterable[Mapping[str, Any]], username: str
) -> list[str]:
    """Choose a user's units from mapping rows matched ignoring capitalisation.

    The mapping can hold usernames that differ only by capitalisation and point
    to different units. Row-level security matches the exact username, so an
    exact match wins and other spellings are used only when there is none.
    """
    matches = list(rows)
    exact = [row["unit_id"] for row in matches if row["username"] == username]
    return exact or [row["unit_id"] for row in matches]


def get_units(unit_ids: Iterable[str]) -> dict[str, OrgUnit]:
    """Return the requested units by id."""
    wanted = sorted(set(unit_ids))
    if not wanted:
        return {}
    query = text(_units_select("toString(o.id) IN :unit_ids")).bindparams(
        bindparam("unit_ids", expanding=True)
    )
    units = [org_unit_from_row(row) for row in _query(query, {"unit_ids": wanted})]
    return {unit.id: unit for unit in units}


def get_top_units() -> list[OrgUnit]:
    """Return the units at the top of the tree."""
    rows = _query(text(_units_select("o.level = :level")), {"level": TOP_LEVEL})
    return [org_unit_from_row(row) for row in rows]


def get_user_units(username: str) -> list[OrgUnit] | None:
    """Return the units mapped to ``username``, or None if they cannot be read.

    An empty list means the user has no unit. Failure and slowness are not
    raised, so feedback can still be sent while ClickHouse is unavailable.
    """
    query = text(
        "SELECT m.username AS username, "  # noqa: S608 - config-quoted identifiers
        "toString(m.org_unit_id) AS unit_id "
        f"FROM {_mapping_table()} AS m FINAL "
        "WHERE lowerUTF8(trimBoth(m.username)) = lowerUTF8(trimBoth(:username))"
    )
    try:
        unit_ids = unit_ids_for_username(
            _query(query, {"username": username}), username
        )
        units = get_units(unit_ids)
    except OrgUnitLookupError:
        logger.warning("Org unit lookup failed for feedback sender", exc_info=True)
        return None
    return sorted(units.values(), key=lambda unit: unit.path)


def get_usernames_by_unit(unit_ids: Iterable[str]) -> dict[str, set[str]]:
    """Return the usernames mapped to each of the requested units."""
    wanted = sorted(set(unit_ids))
    if not wanted:
        return {}
    query = text(
        "SELECT toString(m.org_unit_id) AS unit_id, m.username AS username "  # noqa: S608 - config-quoted identifiers
        f"FROM {_mapping_table()} AS m FINAL "
        "WHERE toString(m.org_unit_id) IN :unit_ids"
    ).bindparams(bindparam("unit_ids", expanding=True))
    usernames: dict[str, set[str]] = {}
    for row in _query(query, {"unit_ids": wanted}):
        usernames.setdefault(row["unit_id"], set()).add(str(row["username"]))
    return usernames


def search_units_below(unit: OrgUnit, term: str, limit: int) -> list[OrgUnit]:
    """Return open units below ``unit`` whose name contains ``term``."""
    level = int(unit.level)
    if level not in LEVELS:
        return []
    query = text(
        _units_select(
            f"o.level{level}id = :unit_id AND toString(o.id) != :unit_id "
            "AND (o.closeddate IS NULL OR o.closeddate > now()) "
            "AND positionCaseInsensitiveUTF8(o.name, :term) > 0",
            "ORDER BY o.level, o.name LIMIT :limit",
        )
    )
    rows = _query(query, {"unit_id": unit.id, "term": term, "limit": limit})
    return [org_unit_from_row(row) for row in rows]
