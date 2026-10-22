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
"""
Context for the dashboard context strip: which data source a tab reads, how
current that source is, and — for DHIS2 tabs — how completely the reports
behind the tab's indicators arrived.

Two kinds of source:

``dhis2``
    Monthly DHIS2 reports. "Data as of" is the latest month whose reporting
    completeness reached the agreed threshold; a newer month still filling up
    is reported separately as in progress. Completeness and timeliness follow
    the Data Quality tab's formula: reports received (on time) ÷ reports
    expected, where expected is the facilities assigned the reporting forms.
    The forms are the ones carrying the tab's indicators' data elements,
    limited to monthly forms still in use (reported within the latest few
    months), so retired, planning and never-used forms do not dilute it.

``annual`` / ``snapshot``
    Surveys and warehouses (EDHS, STEPS, PHEM, blood bank, HR, financing, …)
    have no "reports expected", so only their latest year (or snapshot date)
    is shown, read by a one-value ``SELECT`` configured per source.

Everything here only reads. Every knob is overridable from Flask config —
see ``MOH_CONTEXT_*`` in superset_config.example.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

# Org-unit tree filter column for each hierarchy level (see OrgUnitTreeFilter).
ORG_LEVEL_COLUMNS: dict[str, int] = {
    "region": 2,
    "zone": 3,
    "woreda": 4,
    "phcu": 5,
    "health_post": 6,
}

DEFAULT_COMPLETENESS_THRESHOLD = 80.0
DEFAULT_ACTIVE_FORM_MONTHS = 3

# A source's "query" must return one row with one string column.
DEFAULT_CONTEXT_SOURCES: dict[str, dict[str, Any]] = {
    "dhis2": {"label": "DHIS2", "kind": "dhis2"},
    "echis": {
        "label": "eCHIS",
        "kind": "annual",
        "query": (
            "SELECT concat(p.fiscal_year, ' EFY · ', p.month_name) "
            "FROM moh.monthly_periods AS p WHERE p.period = ("
            "SELECT max(period) FROM echis.indicator_data_values "
            "WHERE match(period, '^[0-9]{6}$'))"
        ),
    },
    "edhs": {
        "label": "EDHS",
        "kind": "annual",
        "query": "SELECT toString(max(survey_year)) FROM moh.edhs_flat",
    },
    "steps": {
        "label": "STEPS survey",
        "kind": "annual",
        "query": "SELECT toString(max(year)) FROM moh.steps2024_ncd_riskfactors",
    },
    "igme": {
        "label": "UN IGME",
        "kind": "annual",
        "query": (
            "SELECT max(year) FROM moh.child_mortality WHERE obs_value IS NOT NULL"
        ),
    },
    "wuenic": {
        "label": "WUENIC",
        "kind": "annual",
        "query": "SELECT max(year) FROM moh.vaccines WHERE coverage IS NOT NULL",
    },
    "malaria": {
        "label": "Malaria risk model",
        "kind": "annual",
        "query": (
            "SELECT concat(p.fiscal_year, ' EFY · ', p.month_name) "
            "FROM moh.monthly_periods AS p "
            "WHERE p.period = (SELECT max(period_text) FROM moh.risk_data)"
        ),
    },
    "tb_incidence": {
        "label": "TB incidence (WHO)",
        "kind": "annual",
        "query": "SELECT toString(max(year)) FROM moh.incidence_trend",
    },
    "phem": {
        "label": "PHEM surveillance",
        "kind": "annual",
        "query": "SELECT max(fiscal_year) FROM moh.disease_surveillance",
    },
    "equity": {
        "label": "Health equity",
        "kind": "annual",
        "query": "SELECT toString(max(year)) FROM moh.simple_measures",
    },
    "blood": {
        "label": "Blood bank",
        "kind": "annual",
        "query": (
            "SELECT y.year_label FROM blood_donation.blood_collection_fact AS f "
            "INNER JOIN blood_donation.year_dim AS y ON y.year_id = f.year_id "
            "WHERE f.blood_collected_units IS NOT NULL "
            "ORDER BY y.calendar_year DESC LIMIT 1"
        ),
    },
    "financing": {
        "label": "Health financing",
        "kind": "annual",
        "query": (
            "SELECT d.year_label FROM health_financing.fact_regional_health_budget "
            "AS f INNER JOIN health_financing.dim_year AS d "
            "ON d.year_key = f.year_key ORDER BY f.year_key DESC LIMIT 1"
        ),
    },
    "workforce": {
        "label": "HR records",
        "kind": "annual",
        "query": (
            "SELECT toString(max(y.reporting_year)) FROM hr.fact_regional_staffing "
            "AS f INNER JOIN hr.dim_reporting_year AS y "
            "ON y.reporting_year_key = f.reporting_year_key"
        ),
    },
    "facilities": {
        "label": "Facility status (HR)",
        "kind": "annual",
        "query": (
            "SELECT toString(max(y.reporting_year)) FROM hr.fact_facility_status "
            "AS f INNER JOIN hr.dim_reporting_year AS y "
            "ON y.reporting_year_key = f.reporting_year_key"
        ),
    },
    "mfr": {
        "label": "Facility registry (MFR)",
        "kind": "snapshot",
        "query": (
            "SELECT formatDateTime(max(_sdc_extracted_at), '%Y-%m-%d') "
            "FROM moh.mfr_facilities"
        ),
    },
    "supply": {
        "label": "Pharmaceutical supply",
        "kind": "annual",
        "query": (
            "SELECT toString(max(year_key)) FROM pharmaceuticals.fact_annual_supply"
        ),
    },
}

# Dashboard id → [(tab path prefix, source keys)]. The most specific (longest)
# matching prefix wins. Tab paths join tab titles outermost first with " / ".
DEFAULT_CONTEXT_TABS: dict[int, list[tuple[str, list[str]]]] = {
    3: [
        ("Summary", ["dhis2"]),
        ("Routine Health Indicators", ["dhis2"]),
        ("Data Quality", ["dhis2"]),
        ("Multi Source / EDHS", ["edhs"]),
        ("Multi Source / IGME", ["igme"]),
        ("Multi Source / MFR", ["mfr"]),
        ("Multi Source / WUEINC", ["wuenic"]),
        ("Triangulation / EDHS vs DHIS2", ["dhis2", "edhs"]),
        ("Triangulation / eCHIS vs DHIS2", ["dhis2", "echis"]),
    ],
    8: [
        ("Services Delivery", ["dhis2"]),
        ("Services Delivery / Maternal", ["dhis2", "edhs"]),
        ("Services Delivery / Neonatal", ["dhis2", "edhs"]),
        ("Services Delivery / Familly Planning", ["dhis2", "edhs"]),
        ("Services Delivery / Malaria", ["malaria"]),
        ("Services Delivery / TB", ["dhis2", "tb_incidence"]),
        ("Services Delivery / NCD / Risk Factors", ["steps"]),
        ("Health Equity", ["equity"]),
        ("Health Financing", ["financing"]),
        ("Health Work Force", ["workforce"]),
        ("Infrastructure", ["facilities", "mfr"]),
        ("PHEM", ["phem"]),
        ("Supply and Logistics", ["supply"]),
        ("Blood Donation", ["blood"]),
    ],
}


def _norm(text: str) -> str:
    return " ".join(str(text).split()).lower()


def resolve_tab_sources(
    tabs_config: dict[Any, list[tuple[str, list[str]]]],
    dashboard_id: Any,
    tab_path: list[str],
) -> list[str]:
    """Source keys for a tab: the longest configured prefix of its path."""
    rules = tabs_config.get(dashboard_id)
    if rules is None:
        rules = tabs_config.get(str(dashboard_id))
    if rules is None and str(dashboard_id).isdigit():
        rules = tabs_config.get(int(dashboard_id))
    if not rules:
        return []
    path = [_norm(part) for part in tab_path if str(part).strip()]
    best: list[str] = []
    best_len = -1
    for prefix, sources in rules:
        parts = [_norm(part) for part in str(prefix).split("/") if part.strip()]
        if len(parts) > best_len and path[: len(parts)] == parts:
            best, best_len = list(sources), len(parts)
    return best


@dataclass
class ContextRequest:
    """What the strip knows about the tab it sits on."""

    dashboard_id: Any = None
    tab_path: list[str] = field(default_factory=list)
    indicators: list[str] = field(default_factory=list)
    indicator_ids: list[str] = field(default_factory=list)
    data_elements: list[str] = field(default_factory=list)
    data_element_ids: list[str] = field(default_factory=list)
    data_sets: list[str] = field(default_factory=list)
    fiscal_years: list[str] = field(default_factory=list)
    quarters: list[str] = field(default_factory=list)
    months: list[str] = field(default_factory=list)
    org_units: dict[str, list[str]] = field(default_factory=dict)

    @property
    def has_reporting_basis(self) -> bool:
        return bool(
            self.indicators
            or self.indicator_ids
            or self.data_elements
            or self.data_element_ids
            or self.data_sets
        )


_MAX_VALUES = 200


def _str_list(value: Any) -> list[str]:
    if value is None:
        return []
    items = value if isinstance(value, (list, tuple)) else [value]
    out: list[str] = []
    for item in items:
        if item is None or isinstance(item, (dict, list, tuple)):
            continue
        text = str(item)
        if text.strip() and text not in out:
            out.append(text)
    return out[:_MAX_VALUES]


def parse_context_request(payload: Any) -> ContextRequest:
    """Validate the client payload; unknown or malformed fields are ignored."""
    if not isinstance(payload, dict):
        return ContextRequest()
    org_raw = payload.get("orgUnits")
    org_units: dict[str, list[str]] = {}
    if isinstance(org_raw, dict):
        for column in ORG_LEVEL_COLUMNS:
            values = _str_list(org_raw.get(column))
            if values:
                org_units[column] = values
    tab_path = [part for part in _str_list(payload.get("tabPath")) if part.strip()]
    return ContextRequest(
        dashboard_id=payload.get("dashboardId"),
        tab_path=tab_path[:10],
        indicators=_str_list(payload.get("indicators")),
        indicator_ids=_str_list(payload.get("indicatorIds")),
        data_elements=_str_list(payload.get("dataElements")),
        data_element_ids=_str_list(payload.get("dataElementIds")),
        data_sets=_str_list(payload.get("dataSets")),
        fiscal_years=_str_list(payload.get("fiscalYears")),
        quarters=_str_list(payload.get("quarters")),
        months=_str_list(payload.get("months")),
        org_units=org_units,
    )


def _placeholders(prefix: str, values: Iterable[str], params: dict[str, Any]) -> str:
    names = []
    for index, value in enumerate(values):
        name = f"{prefix}_{index}"
        params[name] = value
        names.append(f":{name}")
    return ", ".join(names)


def build_reporting_query(
    request: ContextRequest,
    *,
    schema: str,
    active_form_months: int,
    scope_unit: dict[str, Any] | None,
) -> tuple[str, dict[str, Any]]:
    """Per-month received / on-time / expected reports for the tab's forms.

    Values are always bound parameters; only identifiers from server config
    (the schema) and fixed fragments are interpolated — hence the S608
    suppressions below.
    """
    params: dict[str, Any] = {}
    active_months = max(1, int(active_form_months))
    s = f'"{schema}".' if schema else ""

    element_sources: list[str] = []
    if request.indicators:
        names = _placeholders("ind", request.indicators, params)
        element_sources.append(
            f"SELECT data_element_id FROM {s}monthly_indicator_data_elements "  # noqa: S608
            f"WHERE indicator_short_name IN ({names})"
        )
    if request.indicator_ids:
        ids = _placeholders("indid", request.indicator_ids, params)
        element_sources.append(
            f"SELECT data_element_id FROM {s}monthly_indicator_data_elements "  # noqa: S608
            f"WHERE indicator_id IN ({ids})"
        )
    if request.data_elements:
        names = _placeholders("de", request.data_elements, params)
        element_sources.append(
            f"SELECT id AS data_element_id FROM {s}data_elements "  # noqa: S608
            f"WHERE name IN ({names})"
        )
    if request.data_element_ids:
        ids = _placeholders("deid", request.data_element_ids, params)
        element_sources.append(
            f"SELECT id AS data_element_id FROM {s}data_elements "  # noqa: S608
            f"WHERE id IN ({ids})"
        )

    form_sources: list[str] = []
    if element_sources:
        # Monthly forms carrying the elements, still reported recently.
        form_sources.append(
            "SELECT DISTINCT dse.data_set_id AS data_set_id "  # noqa: S608
            f"FROM (SELECT DISTINCT data_set_id, data_element_id "
            f"FROM {s}data_set_elements FINAL) AS dse "
            "WHERE dse.data_element_id IN ("
            + " UNION DISTINCT ".join(element_sources)
            + ") "  # noqa: S608
            f"AND dse.data_set_id IN (SELECT id FROM {s}data_sets "
            "WHERE periodtype = 'Monthly') "
            "AND dse.data_set_id IN (SELECT DISTINCT data_set_id "
            f"FROM {s}monthly_data_set_registration_status "
            "WHERE period IN (SELECT period FROM recent_periods))"
        )
    if request.data_sets:
        # Forms the user picked explicitly (Data Quality tab) are kept as is.
        names = _placeholders("ds", request.data_sets, params)
        form_sources.append(
            f"SELECT id AS data_set_id FROM {s}data_sets "  # noqa: S608
            f"WHERE trimBoth(ifNull(name, '')) IN ({names})"
        )

    scope_clause = ""
    deepest = sorted(request.org_units, key=lambda column: ORG_LEVEL_COLUMNS[column])
    if deepest:
        column = deepest[-1]
        level = ORG_LEVEL_COLUMNS[column]
        trimmed = [value.strip() for value in request.org_units[column]]
        names = _placeholders("org", trimmed, params)
        scope_clause = f"AND trimBoth(ifNull(l{level}name, '')) IN ({names}) "
    elif scope_unit and scope_unit.get("level") in ORG_LEVEL_COLUMNS.values():
        params["scope_id"] = scope_unit["id"]
        scope_clause = f"AND level{int(scope_unit['level'])}id = :scope_id "

    sql = (
        "WITH recent_periods AS ("  # noqa: S608
        "SELECT DISTINCT period "
        f"FROM {s}monthly_data_set_registration_status "
        f"ORDER BY period DESC LIMIT {active_months}"
        "), forms AS (SELECT DISTINCT data_set_id FROM ("
        + " UNION DISTINCT ".join(form_sources)
        + ")), scope AS ("  # noqa: S608
        f"SELECT id FROM {s}org_units "
        "WHERE (closeddate IS NULL OR closeddate > now()) "
        f"{scope_clause}"
        "), expected AS ("
        f"SELECT count() AS expected FROM {s}monthly_org_unit_data_sets FINAL "
        "WHERE data_set_id IN (SELECT data_set_id FROM forms) "
        "AND org_unit_id IN (SELECT id FROM scope)"
        "), received AS ("
        "SELECT period, count() AS received, countIf(timely = 1) AS on_time "
        f"FROM {s}monthly_data_set_registration_status "
        "WHERE data_set_id IN (SELECT data_set_id FROM forms) "
        "AND org_unit_id IN (SELECT id FROM scope) "
        "GROUP BY period"
        ") "
        "SELECT r.period AS period, p.fiscal_year AS fiscal_year, "
        "p.quarter AS quarter, p.quarter_name AS quarter_name, "
        "p.month_name AS month_name, r.received AS received, "
        "r.on_time AS on_time, (SELECT expected FROM expected) AS expected, "
        "(SELECT count() FROM forms) AS form_count "
        "FROM received AS r "
        f"INNER JOIN {s}monthly_periods AS p ON p.period = r.period "
        "ORDER BY r.period"
    )
    return sql, params


def _pct(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return round(100.0 * numerator / denominator, 1)


def _period_info(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "period": str(row["period"]),
        "fiscalYear": str(row.get("fiscal_year") or "") or None,
        "monthName": (str(row.get("month_name") or "").strip() or None),
        "quarterName": (str(row.get("quarter_name") or "").strip() or None),
    }


def _matches_selection(row: dict[str, Any], request: ContextRequest) -> bool:
    if request.fiscal_years and str(row.get("fiscal_year")) not in request.fiscal_years:
        return False
    if request.quarters:
        quarter_values = {
            str(row.get("quarter")),
            str(row.get("quarter_name") or "").strip(),
            f"Q{row.get('quarter')}",
        }
        if not quarter_values & {value.strip() for value in request.quarters}:
            return False
    if request.months and str(row.get("month_name") or "").strip() not in {
        value.strip() for value in request.months
    }:
        return False
    return True


def summarise_reporting(
    rows: list[dict[str, Any]],
    request: ContextRequest,
    threshold: float,
) -> dict[str, Any] | None:
    """Turn per-month report counts into the strip's DHIS2 context.

    ``latestComplete`` is the newest month at or above ``threshold``;
    ``inProgress`` is a newer month still below it. Completeness covers the
    months the period filters select (every month with data when none is
    selected collapses to the latest complete month).
    """
    rows = sorted(
        (row for row in rows if row.get("expected")), key=lambda r: str(r["period"])
    )
    if not rows:
        return None
    expected = float(rows[0]["expected"])
    for row in rows:
        row["_pct"] = _pct(float(row["received"]), float(row["expected"]))

    complete = [row for row in rows if (row["_pct"] or 0) >= threshold]
    latest_complete = complete[-1] if complete else None
    newest = rows[-1]
    in_progress = (
        newest
        if latest_complete is None
        or str(newest["period"]) > str(latest_complete["period"])
        else None
    )

    has_selection = bool(request.fiscal_years or request.quarters or request.months)
    if has_selection:
        selected = [row for row in rows if _matches_selection(row, request)]
    else:
        selected = [latest_complete or newest]
    if not selected:
        completeness = None
    else:
        received = sum(float(row["received"]) for row in selected)
        on_time = sum(float(row["on_time"]) for row in selected)
        denominator = expected * len(selected)
        value = _pct(received, denominator)
        completeness = {
            "value": value,
            "timeliness": _pct(on_time, denominator),
            "months": len(selected),
            "from": _period_info(selected[0]),
            "to": _period_info(selected[-1]),
            "includesInProgress": bool(
                in_progress
                and any(row["period"] == in_progress["period"] for row in selected)
            ),
            "target": threshold,
            "meetsTarget": value is not None and value >= threshold,
        }

    return {
        "latestComplete": _period_info(latest_complete) if latest_complete else None,
        "inProgress": (
            {**_period_info(in_progress), "completeness": in_progress["_pct"]}
            if in_progress
            else None
        ),
        "completeness": completeness,
        "expectedReports": int(expected),
        "forms": int(rows[0].get("form_count") or 0),
    }
