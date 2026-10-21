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
"""Requested periods without data are reported, not rendered as empty reports."""

from __future__ import annotations

from typing import Any

import pytest
from flask import Flask
from werkzeug.exceptions import BadRequest, NotFound

from superset import moh_reports as reports

SECTION = reports.REPORT_SECTIONS[0]
LATEST = "201811"


@pytest.fixture
def stub_queries(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Replace every database helper; `state["kpis"]` controls the result."""
    state: dict[str, Any] = {"kpis": [], "calls": []}

    def top_indicators(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        state["calls"].append(args[2])
        return [dict(kpi) for kpi in state["kpis"]]

    stubs = {
        "_get_database": lambda: object(),
        "_resolve_user_scope": lambda: object(),
        "_resolve_effective_org_unit": lambda *a: ("ET", 1, "Ethiopia", False),
        "_org_unit_options": lambda *a: [],
        "_national_org_unit_id": lambda *a: "ET",
        "_latest_period": lambda *a: LATEST,
        "_fiscal_year_for_period": lambda *a: "2019",
        "_top_indicators": top_indicators,
        "_trend": lambda *a: [],
        "_regional_breakdown": lambda *a: [],
        "_data_freshness": lambda *a: None,
        "_require_login": lambda: None,
    }
    for name, stub in stubs.items():
        monkeypatch.setattr(reports, name, stub)
    return state


def test_requested_period_without_data_is_flagged(stub_queries: dict[str, Any]) -> None:
    payload = reports._report_payload(SECTION, None, "201905")

    assert payload["period"] == "201905"
    assert payload["periodUnavailable"] is True
    assert payload["latestPeriod"] == LATEST


def test_requested_period_with_data_is_not_flagged(
    stub_queries: dict[str, Any],
) -> None:
    stub_queries["kpis"] = [
        {"indicator_id": "i1", "indicator": "ANC", "value": 1, "baseline": None}
    ]

    payload = reports._report_payload(SECTION, None, "201810")

    assert payload["periodUnavailable"] is False
    assert payload["latestPeriod"] is None


def test_default_period_is_never_flagged(stub_queries: dict[str, Any]) -> None:
    payload = reports._report_payload(SECTION, None, None)

    assert payload["period"] == LATEST
    assert payload["periodUnavailable"] is False


@pytest.mark.parametrize(
    "period",
    ["<img src=x onerror=alert(1)>", "2018' OR '1'='1", "20", "2018-12"],
)
def test_malformed_period_is_rejected(
    stub_queries: dict[str, Any], period: str
) -> None:
    with pytest.raises(BadRequest):
        reports._report_payload(SECTION, None, period)
    assert stub_queries["calls"] == []


def test_export_refuses_a_period_without_data(stub_queries: dict[str, Any]) -> None:
    app = Flask(__name__)
    with app.test_request_context(f"/reports/{SECTION.code}/export.csv?period=201905"):
        with pytest.raises(NotFound) as excinfo:
            reports.report_export_csv(SECTION.code)

    assert "No data for period 201905 and Ethiopia." in str(excinfo.value.description)
    assert LATEST in str(excinfo.value.description)


def test_export_succeeds_when_the_period_has_data(
    stub_queries: dict[str, Any],
) -> None:
    stub_queries["kpis"] = [
        {"indicator_id": "i1", "indicator": "ANC", "value": 1, "baseline": None}
    ]
    app = Flask(__name__)
    with app.test_request_context(f"/reports/{SECTION.code}/export.csv?period=201810"):
        response = reports.report_export_csv(SECTION.code)

    assert response.status_code == 200
    assert b"201810" in response.get_data()
