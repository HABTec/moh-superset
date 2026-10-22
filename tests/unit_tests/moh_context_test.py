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
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, Iterator

import pytest
from flask import Flask

from superset import moh_orgunits_api as api
from superset.moh_context import (
    build_reporting_query,
    ContextRequest,
    DEFAULT_CONTEXT_TABS,
    parse_context_request,
    resolve_tab_sources,
    summarise_reporting,
)
from superset.utils import json


def month(
    period: str, fiscal_year: str, name: str, received: int, on_time: int
) -> dict[str, Any]:
    return {
        "period": period,
        "fiscal_year": fiscal_year,
        "quarter": 1,
        "quarter_name": "Hamle to Meskerem (Q1)",
        "month_name": name,
        "received": received,
        "on_time": on_time,
        "expected": 100,
        "form_count": 3,
    }


MONTHS = [
    month("201810", "2018", "Sene", 92, 80),
    month("201811", "2019", "Hamle", 90, 70),
    month("201812", "2019", "Nehase", 85, 75),
    month("201901", "2019", "Meskerem", 64, 64),
]


def test_tab_sources_use_the_most_specific_prefix() -> None:
    tabs = DEFAULT_CONTEXT_TABS
    assert resolve_tab_sources(tabs, 8, ["Services Delivery", "HIV"]) == ["dhis2"]
    assert resolve_tab_sources(tabs, 8, ["Services Delivery", "Maternal"]) == [
        "dhis2",
        "edhs",
    ]
    assert resolve_tab_sources(tabs, 8, ["Services Delivery", "Malaria"]) == ["malaria"]
    assert resolve_tab_sources(tabs, "3", ["Multi Source", "EDHS"]) == ["edhs"]
    assert resolve_tab_sources(tabs, 3, ["summary", "Maternal  Health"]) == ["dhis2"]


def test_tab_sources_are_empty_for_unknown_tabs_and_dashboards() -> None:
    assert resolve_tab_sources(DEFAULT_CONTEXT_TABS, 8, ["Elsewhere"]) == []
    assert resolve_tab_sources(DEFAULT_CONTEXT_TABS, 99, ["Summary"]) == []


def test_parse_keeps_known_fields_and_drops_malformed_values() -> None:
    request = parse_context_request(
        {
            "dashboardId": 3,
            "tabPath": ["Summary", "EPI", ""],
            "indicators": ["Penta 3 Coverage", "Penta 3 Coverage", None, {"x": 1}],
            "orgUnits": {"zone": ["Arsi Zone"], "unknown": ["x"], "region": "Oromia"},
            "fiscalYears": 2019,
        }
    )
    assert request.tab_path == ["Summary", "EPI"]
    assert request.indicators == ["Penta 3 Coverage"]
    assert request.org_units == {"zone": ["Arsi Zone"], "region": ["Oromia"]}
    assert request.fiscal_years == ["2019"]
    assert parse_context_request("not a dict") == ContextRequest()


def test_reporting_query_binds_every_value() -> None:
    request = ContextRequest(
        indicators=["ANC'; DROP TABLE x;--"],
        data_sets=["01.1 - Reproductive"],
        org_units={"region": ["Amhara Region "], "zone": ["North Gondar "]},
    )
    sql, params = build_reporting_query(
        request, schema="moh", active_form_months=3, scope_unit=None
    )
    assert "DROP TABLE" not in sql
    assert params["ind_0"] == "ANC'; DROP TABLE x;--"
    assert params["ds_0"] == "01.1 - Reproductive"
    # The deepest selected level scopes the units; names are trimmed.
    assert "trimBoth(ifNull(l3name, '')) IN (:org_0)" in sql
    assert params["org_0"] == "North Gondar"
    # Only monthly forms still reported in the latest months count.
    assert "periodtype = 'Monthly'" in sql
    assert "LIMIT 3" in sql


def test_reporting_query_falls_back_to_the_users_area() -> None:
    sql, params = build_reporting_query(
        ContextRequest(indicators=["CAR"]),
        schema="moh",
        active_form_months=3,
        scope_unit={"id": "R1", "level": 2},
    )
    assert "level2id = :scope_id" in sql
    assert params["scope_id"] == "R1"


def test_without_a_period_selection_completeness_is_the_latest_complete_month() -> None:
    result = summarise_reporting([dict(m) for m in MONTHS], ContextRequest(), 80.0)
    assert result is not None
    assert result["latestComplete"]["period"] == "201812"
    assert result["inProgress"]["period"] == "201901"
    assert result["inProgress"]["completeness"] == 64.0
    completeness = result["completeness"]
    assert completeness["value"] == 85.0
    assert completeness["timeliness"] == 75.0
    assert completeness["meetsTarget"] is True
    assert completeness["includesInProgress"] is False


def test_a_selected_year_pools_its_months_and_flags_the_partial_one() -> None:
    result = summarise_reporting(
        [dict(m) for m in MONTHS], ContextRequest(fiscal_years=["2019"]), 80.0
    )
    assert result is not None
    completeness = result["completeness"]
    assert completeness["months"] == 3
    assert completeness["value"] == 79.7  # (90 + 85 + 64) / 300
    assert completeness["meetsTarget"] is False
    assert completeness["includesInProgress"] is True
    assert completeness["from"]["monthName"] == "Hamle"
    assert completeness["to"]["monthName"] == "Meskerem"


def test_quarter_and_month_selections_match_names_or_numbers() -> None:
    by_quarter = summarise_reporting(
        [dict(m) for m in MONTHS], ContextRequest(quarters=["Q1"]), 80.0
    )
    assert by_quarter is not None
    assert by_quarter["completeness"]["months"] == 4
    by_month = summarise_reporting(
        [dict(m) for m in MONTHS], ContextRequest(months=["Nehase"]), 80.0
    )
    assert by_month is not None
    assert by_month["completeness"]["value"] == 85.0


def test_no_month_reaching_the_target_reports_the_newest_as_in_progress() -> None:
    rows = [month("201901", "2019", "Meskerem", 40, 30)]
    result = summarise_reporting(rows, ContextRequest(), 80.0)
    assert result is not None
    assert result["latestComplete"] is None
    assert result["inProgress"]["period"] == "201901"
    assert result["completeness"]["value"] == 40.0


def test_no_expected_reports_means_no_reporting_context() -> None:
    assert summarise_reporting([], ContextRequest(), 80.0) is None
    empty = {**MONTHS[0], "expected": 0}
    assert summarise_reporting([empty], ContextRequest(), 80.0) is None


class FakeResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = [SimpleNamespace(_mapping=row) for row in rows]

    def all(self) -> list[SimpleNamespace]:
        return self._rows

    def first(self) -> SimpleNamespace | None:
        return self._rows[0] if self._rows else None


class FakeDatabase:
    def __init__(self, responses: list[list[dict[str, Any]]]) -> None:
        self.responses = list(responses)
        self.queries: list[tuple[str, dict[str, Any]]] = []

    @contextmanager
    def get_sqla_engine(self) -> Iterator[Any]:
        database = self

        class Conn:
            def execute(self, sql: Any, params: dict[str, Any]) -> FakeResult:
                database.queries.append((str(sql), params))
                return FakeResult(database.responses.pop(0))

        @contextmanager
        def connect() -> Iterator[Conn]:
            yield Conn()

        yield SimpleNamespace(connect=connect, dispose=lambda: None)


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> Flask:
    flask_app = Flask(__name__)
    flask_app.config["MOH_ORG_UNITS_CACHE_TTL"] = 0
    flask_app.register_blueprint(api.moh_orgunits_bp)
    monkeypatch.setattr(
        api, "current_user", SimpleNamespace(is_authenticated=True, username="u")
    )
    monkeypatch.setattr(api, "_scope_unit", lambda: None)
    api._tab_context_cache.clear()
    api._source_value_cache.clear()
    return flask_app


def get_context(app: Flask, payload: dict[str, Any]) -> Any:
    return app.test_client().get(
        "/api/v1/moh/dhis2/tab-context", query_string={"q": json.dumps(payload)}
    )


def test_endpoint_reports_dhis2_completeness_and_a_survey_year(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = FakeDatabase([[dict(m) for m in MONTHS], [{"value": "2024"}]])
    monkeypatch.setattr(api, "_get_database", lambda: database)

    response = get_context(
        app,
        {
            "dashboardId": 8,
            "tabPath": ["Services Delivery", "Maternal"],
            "indicators": ["Skilled Birth Attendance"],
        },
    )

    assert response.status_code == 200
    body = response.json
    dhis2, edhs = body["sources"]
    assert dhis2["key"] == "dhis2"
    assert dhis2["latestPeriod"]["monthName"] == "Nehase"
    assert dhis2["inProgress"]["monthName"] == "Meskerem"
    assert edhs == {"key": "edhs", "label": "EDHS", "kind": "annual", "latest": "2024"}
    assert body["completeness"]["value"] == 85.0
    assert body["basis"] == {"forms": 3, "expectedReports": 100}
    assert database.queries[0][1]["ind_0"] == "Skilled Birth Attendance"


def test_endpoint_without_indicators_reports_latest_data_only(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    latest = {
        "period": "201902",
        "fiscal_year": "2019",
        "quarter": 2,
        "quarter_name": "Tikimt to Tahsas (Q2)",
        "month_name": "Tikimt",
    }
    monkeypatch.setattr(api, "_get_database", lambda: FakeDatabase([[latest]]))

    body = get_context(
        app, {"dashboardId": 8, "tabPath": ["Services Delivery", "HIV"]}
    ).json

    assert body["completeness"] is None
    assert body["sources"][0]["basis"] == "latest_data"
    assert body["sources"][0]["latestPeriod"]["monthName"] == "Tikimt"


def test_endpoint_survives_a_failing_source(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken() -> Any:
        raise RuntimeError("warehouse down")

    monkeypatch.setattr(api, "_get_database", broken)

    body = get_context(app, {"dashboardId": 8, "tabPath": ["PHEM"]}).json

    assert body["sources"] == [
        {"key": "phem", "label": "PHEM surveillance", "kind": "annual"}
    ]


def test_endpoint_rejects_bad_json_and_anonymous_users(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = app.test_client()
    bad = client.get("/api/v1/moh/dhis2/tab-context", query_string={"q": "{"})
    assert bad.status_code == 400
    monkeypatch.setattr(api, "current_user", SimpleNamespace(is_authenticated=False))
    assert get_context(app, {"dashboardId": 8}).status_code == 401


def test_reporting_query_accepts_data_element_names_and_ids() -> None:
    request = parse_context_request(
        {"dataElements": ["MAT_ANC 1st"], "dataElementIds": ["lotDArt3TsU"]}
    )
    assert request.has_reporting_basis
    sql, params = build_reporting_query(
        request, schema="moh", active_form_months=3, scope_unit=None
    )
    assert params["de_0"] == "MAT_ANC 1st"
    assert params["deid_0"] == "lotDArt3TsU"
    assert "WHERE id IN (:deid_0)" in sql
