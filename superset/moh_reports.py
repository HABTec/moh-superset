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
"""Routine Reporting: report-first workflow (Annotated UI Mockup 02).

Select a report family -> select Period + Organisation Unit -> preview ->
generate PDF / Excel / CSV. The report catalogue is not hand-curated: it is
the eight `section` values already used by `dataset_core_v2` and
`monthly_indicator_data_elements` (the same taxonomy every existing MoH
dashboard already reads), so a new report family shows up here automatically
once it exists in that data — no code change needed to add one.

Role-based scope (mockup section 4) is enforced the same way the rest of the
MoH portal enforces it: by resolving the logged-in user's assigned org unit
via `dim_user_orgunit`, exactly as `moh_orgunits_api.get_my_unit` does. A
user below national level can only select an org unit inside their own
subtree; a request for one outside it is clamped to their own unit rather
than rejected outright, so a stale link never breaks the page — the page
says so visibly when that happens.

Registered with Flask via the BLUEPRINTS list in superset_config.py.
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from flask import (
    abort,
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    Response,
)
from flask_login import current_user
from sqlalchemy import text

from superset.moh_calendar import current_period_key

logger = logging.getLogger(__name__)

moh_reports_bp = Blueprint(
    "moh_reports",
    __name__,
    url_prefix="/reports",
    template_folder="templates",
)


# ---------------------------------------------------------------------------
# The report catalogue — derived from the `section` values already used by
# dataset_core_v2 / monthly_indicator_data_elements, not invented here.
# `grains` lists which period granularities a report offers. Every section
# today only lists "monthly": dataset_core_v2, which every query below reads,
# only carries monthly-shaped periods (YYYYMM); quarterly_indicator_data_elements
# confirms 4 of these 8 sections DO have quarterly indicators defined, but
# querying them means reading quarterly_nov_data_values/-periods instead, which
# this module does not do yet — so "quarterly" is left off rather than shown
# as an option that would come back empty.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReportSection:
    code: str
    section: str  # exact `section` column value in dataset_core_v2
    title: str
    subtitle: str
    grains: tuple[str, ...] = ("monthly",)
    # Indicators to lead the report with, in this order. `None` means no
    # curated pick exists yet, so the report falls back to the first few
    # indicators alphabetically — deterministic, but not a judgement this
    # code is positioned to make. Only MCAH has one, seeded from the four
    # indicators the mockup itself names (ANC coverage, Skilled Birth
    # Attendance, PNC) that also exist verbatim in the data; this is a
    # reasonable placeholder, not a Ministry-confirmed indicator set — swap
    # it, or add the rest, once programme owners confirm what each report
    # should lead with.
    headline_indicators: tuple[str, ...] | None = None


REPORT_SECTIONS: list[ReportSection] = [
    ReportSection(
        "mcah",
        "MCAH-Maternal, Child, and Adolescent Health",
        "Maternal, Child & Adolescent Health",
        "Maternal, newborn, child and adolescent health",
        headline_indicators=(
            "ANC 4+ Contacts Coverage",
            "ANC 8+ Contact Coverage",
            "Skilled Birth Attendance",
            "PNC Coverage (0-2 days)",
        ),
    ),
    ReportSection(
        "dpc",
        "DPC-Disease Prevention Control",
        "Disease Prevention & Control",
        "TB, malaria, NCDs and other disease programmes",
    ),
    ReportSection(
        "ms",
        "MS-Medical Services and Service Quality",
        "Medical Services & Service Quality",
        "Emergency, surgical, referral and service access",
    ),
    ReportSection(
        "ce-phc",
        "CE-PHC-Community Engagement and Primary Health Care",
        "Community Engagement & Primary Health Care",
        "Health extension and WASH programmes",
    ),
    ReportSection(
        "hiv",
        "HIV-HIV AIDS Prevention and Control",
        "HIV/AIDS Prevention & Control",
        "Prevention and treatment programme reporting",
    ),
    ReportSection(
        "his",
        "HIS-Health Information System",
        "Health Information System",
        "Reporting and decision-support indicators",
    ),
    ReportSection(
        "nut",
        "NUT-Nutrition",
        "Nutrition",
        "Prevention and treatment programme reporting",
    ),
    ReportSection(
        "pmd",
        "PMD-Pharmaceutical and Medical Devices",
        "Pharmaceutical & Medical Devices",
        "Essential drug and commodity availability",
    ),
]

_SECTIONS_BY_CODE: dict[str, ReportSection] = {s.code: s for s in REPORT_SECTIONS}


def _get_report_section(code: str) -> ReportSection:
    section = _SECTIONS_BY_CODE.get(code)
    if section is None:
        abort(404, f"Unknown report '{code}'")
    return section


# ---------------------------------------------------------------------------
# Config / connection helpers — same config keys as moh_orgunits_api.py, so
# one deployment only sets MOH_ORG_UNITS_DB_NAME etc. once.
# ---------------------------------------------------------------------------


def _db_name() -> str:
    return current_app.config.get("MOH_ORG_UNITS_DB_NAME", "MOH_Click_Hhouse")


def _schema() -> str:
    return current_app.config.get("MOH_ORG_UNITS_SCHEMA", "moh")


def _qualified(table: str) -> str:
    schema = _schema()
    return f'"{schema}"."{table}"' if schema else f'"{table}"'


def _get_database():
    from superset import db as superset_db  # pylint: disable=import-outside-toplevel
    from superset.models.core import Database  # pylint: disable=import-outside-toplevel

    name = _db_name()
    database = (
        superset_db.session.query(Database).filter_by(database_name=name).first()
    )
    if database is None:
        abort(503, f"Database '{name}' is not configured.")
    return database


def _require_login():
    if not getattr(current_user, "is_authenticated", False):
        return redirect(f"/login/?next={request.path}")
    return None


# ---------------------------------------------------------------------------
# Role-based scope — resolves the logged-in user's org unit the same way
# moh_orgunits_api.get_my_unit does, then constrains report queries to it.
# ---------------------------------------------------------------------------


@dataclass
class UserScope:
    org_unit_id: str | None
    level: int
    level_ids: dict[int, str] = field(default_factory=dict)
    is_national: bool = False


_LEVEL_ID_COLS = [
    "level1id",
    "level2id",
    "level3id",
    "level4id",
    "level5id",
    "level6id",
]


def _resolve_user_scope() -> UserScope:
    """The logged-in user's assigned org unit, level, and ancestor chain.

    An admin, or a user with no dim_user_orgunit assignment, is treated as
    national (unrestricted) — matching how MoHSecurityManager already treats
    admins and how the dashboards' own RLS resolves an unassigned user.
    """
    is_admin = bool(
        hasattr(current_app, "appbuilder")
        and current_app.appbuilder.sm.is_admin()
    )
    database = _get_database()
    cols = ", ".join(_LEVEL_ID_COLS)
    with database.get_sqla_engine() as engine:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    f"SELECT ou.id, ou.level, {cols} "
                    f"FROM {_qualified('dim_user_orgunit')} AS uo "
                    f"INNER JOIN {_qualified('org_units')} AS ou "
                    "ON toString(uo.org_unit_id) = toString(ou.id) "
                    "WHERE lower(trimBoth(uo.username)) = lower(trimBoth(:username)) "
                    "ORDER BY ou.level LIMIT 1"
                ),
                {"username": getattr(current_user, "username", "")},
            ).first()
    if row is None:
        return UserScope(org_unit_id=None, level=1, is_national=True)
    mapping = row._mapping
    level_ids = {
        i + 1: mapping[col]
        for i, col in enumerate(_LEVEL_ID_COLS)
        if mapping[col]
    }
    return UserScope(
        org_unit_id=mapping["id"],
        level=mapping["level"],
        level_ids=level_ids,
        is_national=is_admin or mapping["level"] <= 1,
    )


def _national_org_unit_id(database) -> str | None:
    with database.get_sqla_engine() as engine:
        with engine.connect() as conn:
            row = conn.execute(
                text(f"SELECT id FROM {_qualified('org_units')} WHERE level=1 LIMIT 1")
            ).first()
    return row[0] if row else None


def _org_unit_in_scope(scope: UserScope, org_unit_id: str, org_unit_level: int) -> bool:
    """Whether `org_unit_id` (at `org_unit_level`) is inside the user's subtree."""
    if scope.is_national:
        return True
    if org_unit_level < scope.level:
        return False
    if org_unit_level == scope.level:
        return org_unit_id == scope.org_unit_id
    return (
        scope.level_ids.get(scope.level) is not None
        and org_unit_id in scope.level_ids.values()
    )


def _org_unit_name_and_level(org_unit_id: str, database) -> tuple[str, int] | None:
    with database.get_sqla_engine() as engine:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT name, level "
                    f"FROM {_qualified('org_units')} WHERE id=:id LIMIT 1"
                ),
                {"id": org_unit_id},
            ).first()
    if row is None:
        return None
    return (row[0] or "").strip(), row[1]


def _resolve_effective_org_unit(
    scope: UserScope, requested_id: str | None, database
) -> tuple[str, int, str, bool]:
    """(org_unit_id, level, name, was_clamped) — the org unit a report actually uses.

    Falls back to the user's own unit (or national, for a national user) when
    nothing was requested. A requested unit's level is always looked up and
    checked against the user's scope — never trusted from the request — and
    an out-of-scope or unknown id is clamped to the user's own unit rather
    than raising, so a stale or tampered link degrades instead of leaking
    another area's data.
    """
    default_id = scope.org_unit_id or _national_org_unit_id(database)
    default_level = scope.level if scope.org_unit_id else 1
    default_name_and_level = (
        _org_unit_name_and_level(default_id, database) if default_id else None
    )
    default_name = (
        default_name_and_level[0] if default_name_and_level else (default_id or "")
    )

    if not requested_id:
        return default_id, default_level, default_name, False

    requested = _org_unit_name_and_level(requested_id, database)
    if requested is None or not _org_unit_in_scope(scope, requested_id, requested[1]):
        return default_id, default_level, default_name, True

    name, level = requested
    return requested_id, level, name, False


# ---------------------------------------------------------------------------
# Report data — every query filters on `orgunit` first (dataset_core_v2's
# leading sort-key column), keeping each one a small, fast lookup instead of
# a scan of an 875-million-row table. AVG(), never SUM() or count(): the
# table carries known duplicate rows per (orgunit, indicator, period), and
# AVG() is unaffected by that fan-out while SUM() would badly inflate totals.
# ---------------------------------------------------------------------------

_FACT_TABLE = "dataset_core_v2"
_REGION_LEVEL = 2


def _latest_period(section: ReportSection, org_unit_id: str, database) -> str | None:
    current_fy_period = current_period_key(date.today())
    with database.get_sqla_engine() as engine:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    f"SELECT max(period) FROM {_qualified(_FACT_TABLE)} "
                    "WHERE orgunit = :org_unit AND section = :section "
                    "AND period < :current_period"
                ),
                {
                    "org_unit": org_unit_id,
                    "section": section.section,
                    "current_period": current_fy_period,
                },
            ).first()
    return row[0] if row and row[0] else None


def _fiscal_year_for_period(period: str, database) -> str:
    """The real fiscal_year for a period key, looked up rather than guessed.

    dataset_core_v2 period keys are "YYYYMM", but that "YYYY" is NOT always
    the fiscal year: the Ethiopian fiscal year starts in Hamle (month 11), so
    periods ending "11" and "12" (Hamle, Nehase) belong to the FOLLOWING
    fiscal year — period 201812 is fiscal_year 2019, not 2018. Slicing the
    string silently produced the wrong year for exactly those two months
    every year, which zeroed out every query filtered by both period and a
    guessed fiscal_year. monthly_periods carries the real mapping.
    """
    with database.get_sqla_engine() as engine:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    f"SELECT fiscal_year FROM {_qualified('monthly_periods')} "
                    "WHERE period = :period LIMIT 1"
                ),
                {"period": period},
            ).first()
    if row and row[0]:
        return row[0]
    # Defensive fallback only — every period dataset_core_v2 actually uses is
    # expected to exist in monthly_periods.
    logger.warning(
        "Period %s not found in monthly_periods; guessing fiscal_year", period
    )
    return period[:4] if period and len(period) >= 4 else period


def _top_indicators(
    section: ReportSection, org_unit_id: str, period: str, database, limit: int = 4
) -> list[dict[str, Any]]:
    """The indicators this report leads with.

    Filtered by `period` alone — it is already a unique key (confirmed: no
    period in dataset_core_v2 maps to more than one fiscal_year), so adding
    a separately-derived fiscal_year filter only risks disagreeing with it.

    Every row in dataset_core_v2 is duplicated a large, roughly uniform
    number of times per (indicator, period) — see MOH_CUSTOMIZATIONS notes —
    so ordering by row count ties almost everywhere and effectively falls
    back to alphabetical anyway. Rather than imply that count means anything,
    this either follows the section's curated `headline_indicators` (in that
    order) or is explicitly alphabetical.
    """
    base_where = (
        "WHERE orgunit = :org_unit AND section = :section AND period = :period "
    )
    params: dict[str, Any] = {
        "org_unit": org_unit_id,
        "section": section.section,
        "period": period,
    }
    order_by = "ORDER BY indicator ASC LIMIT :limit"
    params["limit"] = limit
    if section.headline_indicators:
        placeholders = ", ".join(
            f":indicator_{i}" for i in range(len(section.headline_indicators))
        )
        params.update(
            {
                f"indicator_{i}": name
                for i, name in enumerate(section.headline_indicators)
            }
        )
        base_where += f"AND indicator IN ({placeholders}) "
        order_by = ""  # re-ordered in Python to match headline_indicators exactly

    with database.get_sqla_engine() as engine:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT indicator, indicator_id, "
                    "avg(value) AS val, avg(baseline_value) AS baseline "
                    f"FROM {_qualified(_FACT_TABLE)} "
                    f"{base_where}"
                    "GROUP BY indicator, indicator_id "
                    f"{order_by}"
                ),
                params,
            ).all()

    results = [
        {
            "indicator": row.indicator,
            "indicator_id": row.indicator_id,
            "value": round(row.val, 1) if row.val is not None else None,
            "baseline": round(row.baseline, 1) if row.baseline is not None else None,
        }
        for row in rows
    ]
    if section.headline_indicators:
        order = {name: i for i, name in enumerate(section.headline_indicators)}
        results.sort(key=lambda item: order.get(item["indicator"], len(order)))
    return results


def _trend(
    section: ReportSection,
    org_unit_id: str,
    indicator_id: str,
    fiscal_year: str,
    database,
) -> list[dict[str, Any]]:
    # Ordered by fiscal_month_number, not the raw calendar `month` column:
    # the Ethiopian fiscal year starts in Hamle (calendar month 11), so
    # sorting by `month` puts Meskerem (calendar 1, fiscal 3rd) first and
    # Hamle/Nehase (calendar 11-12, fiscal 1st-2nd) last — backwards.
    with database.get_sqla_engine() as engine:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT fiscal_month_number, any(month_name) AS month_name, "
                    "avg(value) AS val "
                    f"FROM {_qualified(_FACT_TABLE)} "
                    "WHERE orgunit = :org_unit AND section = :section "
                    "AND indicator_id = :indicator_id AND fiscal_year = :fiscal_year "
                    "GROUP BY fiscal_month_number ORDER BY fiscal_month_number"
                ),
                {
                    "org_unit": org_unit_id,
                    "section": section.section,
                    "indicator_id": indicator_id,
                    "fiscal_year": fiscal_year,
                },
            ).all()
    return [
        {
            "month": row.fiscal_month_number,
            "monthName": (row.month_name or "").strip(),
            "value": round(row.val, 1) if row.val is not None else None,
        }
        for row in rows
    ]


def _region_ids(database) -> list[tuple[str, str]]:
    with database.get_sqla_engine() as engine:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT id, name FROM {_qualified('org_units')} "
                    f"WHERE level = {_REGION_LEVEL} ORDER BY name"
                )
            ).all()
    return [(row[0], (row[1] or "").strip()) for row in rows]


def _org_unit_options(
    scope: UserScope, national_id: str | None, database
) -> list[dict[str, Any]]:
    """Org units offered in the report page's selector.

    A national user (or admin) gets National plus every region. A user
    scoped below national only ever has their own unit to pick from — the
    query itself accepts any unit id, but the visible picker only ever
    offers the ones _org_unit_in_scope would accept anyway.
    """
    if scope.is_national:
        options = []
        if national_id:
            options.append(
                {"id": national_id, "name": "National / Ethiopia", "level": 1}
            )
        options.extend(
            {"id": region_id, "name": name, "level": _REGION_LEVEL}
            for region_id, name in _region_ids(database)
        )
        return options
    if scope.org_unit_id:
        found = _org_unit_name_and_level(scope.org_unit_id, database)
        name = found[0] if found else scope.org_unit_id
        return [{"id": scope.org_unit_id, "name": name, "level": scope.level}]
    return []


def _regional_breakdown(
    section: ReportSection,
    indicator_id: str,
    period: str,
    scope: UserScope,
    database,
) -> list[dict[str, Any]]:
    """One row per region, or the user's own region if scoped below national.

    Filtered by `period` alone — see the note on _top_indicators for why a
    separately-derived fiscal_year filter is redundant and risks zeroing
    everything out for Hamle/Nehase (the two months whose numeric-looking
    "year" prefix does not match their real fiscal_year).
    """
    if scope.is_national:
        region_ids = [region_id for region_id, _name in _region_ids(database)]
    elif scope.level == _REGION_LEVEL and scope.org_unit_id:
        region_ids = [scope.org_unit_id]
    elif scope.level_ids.get(_REGION_LEVEL):
        region_ids = [scope.level_ids[_REGION_LEVEL]]
    else:
        return []

    # Built as individual :region_N placeholders rather than a single
    # `IN :region_ids` with a tuple value — the latter needs SQLAlchemy's
    # expanding-bindparam support, which is not reliable across every
    # text()/dialect combination; explicit placeholders work everywhere
    # (same pattern as _cbmp_path_clause in moh_orgunits_api.py).
    region_placeholders = ", ".join(f":region_{i}" for i in range(len(region_ids)))
    region_params = {f"region_{i}": value for i, value in enumerate(region_ids)}
    with database.get_sqla_engine() as engine:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT org_unit_name, avg(value) AS val "
                    f"FROM {_qualified(_FACT_TABLE)} "
                    f"WHERE orgunit IN ({region_placeholders}) AND section = :section "
                    "AND indicator_id = :indicator_id AND period = :period "
                    "GROUP BY org_unit_name ORDER BY val DESC"
                ),
                {
                    **region_params,
                    "section": section.section,
                    "indicator_id": indicator_id,
                    "period": period,
                },
            ).all()
    return [
        {
            "region": (row.org_unit_name or "").strip(),
            "value": round(row.val, 1) if row.val is not None else None,
        }
        for row in rows
    ]


def _data_freshness(section: ReportSection, org_unit_id: str, database) -> str | None:
    with database.get_sqla_engine() as engine:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT max(dw_lastupdated) "
                    f"FROM {_qualified('indicator_data_values')} "
                    "WHERE orgunit = :org_unit"
                ),
                {"org_unit": org_unit_id},
            ).first()
    return row[0].isoformat() if row and row[0] else None


def _report_payload(
    section: ReportSection,
    requested_org_unit: str | None,
    requested_period: str | None,
) -> dict[str, Any]:
    database = _get_database()
    scope = _resolve_user_scope()
    org_unit_id, org_unit_level, org_unit_name, clamped = _resolve_effective_org_unit(
        scope, requested_org_unit, database
    )
    org_unit_options = _org_unit_options(
        scope, _national_org_unit_id(database), database
    )
    period = requested_period or _latest_period(section, org_unit_id, database)
    if not period:
        return {
            "section": section.code,
            "title": section.title,
            "orgUnit": {
                "id": org_unit_id,
                "level": org_unit_level,
                "name": org_unit_name,
            },
            "orgUnitOptions": org_unit_options,
            "grains": list(section.grains),
            "period": None,
            "clamped": clamped,
            "kpis": [],
            "dataAsOf": None,
        }
    fiscal_year = _fiscal_year_for_period(period, database)
    kpis = _top_indicators(section, org_unit_id, period, database)
    # Every KPI gets its own trend and regional breakdown, not just the
    # first — a report meant to be read start to finish (especially once
    # printed) should not need a selector to see the other three.
    for kpi in kpis:
        kpi["trend"] = _trend(
            section, org_unit_id, kpi["indicator_id"], fiscal_year, database
        )
        kpi["regional"] = _regional_breakdown(
            section, kpi["indicator_id"], period, scope, database
        )
    return {
        "section": section.code,
        "title": section.title,
        "orgUnit": {"id": org_unit_id, "level": org_unit_level, "name": org_unit_name},
        "orgUnitOptions": org_unit_options,
        "grains": list(section.grains),
        "period": period,
        "fiscalYear": fiscal_year,
        "clamped": clamped,
        "kpis": kpis,
        "dataAsOf": _data_freshness(section, org_unit_id, database),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def _payload_from_request(section: ReportSection) -> dict[str, Any]:
    return _report_payload(
        section, request.args.get("org_unit"), request.args.get("period")
    )


@moh_reports_bp.route("/")
def catalogue():
    if (denied := _require_login()) is not None:
        return denied
    return render_template("superset/reports_catalogue.html", sections=REPORT_SECTIONS)


@moh_reports_bp.route("/<code>/")
def report_view(code: str):
    if (denied := _require_login()) is not None:
        return denied
    section = _get_report_section(code)
    payload = _payload_from_request(section)
    return render_template(
        "superset/report_view.html",
        section=section,
        sections=REPORT_SECTIONS,
        report=payload,
    )


@moh_reports_bp.route("/<code>/data")
def report_data(code: str):
    if (denied := _require_login()) is not None:
        return denied
    section = _get_report_section(code)
    payload = _payload_from_request(section)
    return jsonify(payload)


def _export_rows(payload: dict[str, Any]) -> list[list[Any]]:
    rows: list[list[Any]] = [
        ["Report", payload["title"]],
        ["Period", payload.get("period") or "Not available"],
        ["Organisation unit", payload["orgUnit"]["name"]],
        ["Generated", date.today().isoformat()],
        [],
        ["Indicator", "Value", "Baseline"],
    ]
    for kpi in payload["kpis"]:
        rows.append([kpi["indicator"], kpi["value"], kpi["baseline"]])
    for kpi in payload["kpis"]:
        if not kpi.get("regional"):
            continue
        rows.append([])
        rows.append([f"{kpi['indicator']} by region", "Value"])
        for item in kpi["regional"]:
            rows.append([item["region"], item["value"]])
    return rows


@moh_reports_bp.route("/<code>/export.csv")
def report_export_csv(code: str):
    if (denied := _require_login()) is not None:
        return denied
    section = _get_report_section(code)
    payload = _payload_from_request(section)
    buffer = io.StringIO()
    csv.writer(buffer).writerows(_export_rows(payload))
    response = Response(buffer.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{section.code}-report.csv"'
    )
    return response


@moh_reports_bp.route("/<code>/export.xlsx")
def report_export_xlsx(code: str):
    if (denied := _require_login()) is not None:
        return denied
    try:
        from openpyxl import Workbook  # pylint: disable=import-outside-toplevel
    except ImportError:
        abort(503, "Excel export requires the openpyxl package.")
    section = _get_report_section(code)
    payload = _payload_from_request(section)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = section.title[:31]
    for row in _export_rows(payload):
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    response = Response(
        buffer.read(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{section.code}-report.xlsx"'
    )
    return response


@moh_reports_bp.route("/<code>/export.pdf")
def report_export_pdf(code: str):
    """Render the report page to PDF.

    Reuses the exact Playwright launch/auth sequence
    `WebDriverPlaywright.get_screenshot` uses for Superset's own scheduled
    alert screenshots (`superset/utils/webdriver.py`) — same launch args,
    same `WebDriverPlaywright.auth()` cookie forwarding for the current
    session — swapping only the final capture call for `page.pdf()`.
    """
    if (denied := _require_login()) is not None:
        return denied
    section = _get_report_section(code)  # validate before spending a browser launch
    try:
        from playwright.sync_api import (
            sync_playwright,  # pylint: disable=import-outside-toplevel
        )

        from superset.utils.webdriver import (
            WebDriverPlaywright,  # pylint: disable=import-outside-toplevel
        )
    except ImportError:
        logger.exception("PDF export dependencies are unavailable")
        abort(
            503,
            "PDF export needs Playwright installed on the server "
            "(pip install playwright && playwright install chromium --with-deps).",
        )

    base_path = request.path.rsplit("/export.pdf", 1)[0]
    target_url = f"{request.url_root.rstrip('/')}{base_path}/"
    query = request.query_string.decode("utf-8")
    target_url = f"{target_url}?{query}&print=1" if query else f"{target_url}?print=1"

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                args=current_app.config["WEBDRIVER_OPTION_ARGS"]
            )
            context = browser.new_context(bypass_csp=True)
            WebDriverPlaywright.auth(current_user, context)
            page = context.new_page()
            page.goto(target_url, wait_until="networkidle")
            pdf_bytes = page.pdf(format="A4", print_background=True)
            browser.close()
    except Exception:  # pylint: disable=broad-except
        logger.exception("PDF export failed for report %s", code)
        abort(
            503,
            "Could not generate the PDF. The report page itself still works — "
            "try Excel or CSV, or check the screenshot service configuration.",
        )

    response = Response(pdf_bytes, mimetype="application/pdf")
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{section.code}-report.pdf"'
    )
    return response
