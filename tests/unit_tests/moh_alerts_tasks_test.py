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
"""Each alert run records what it flagged and what every email contained."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from superset.moh_alerts import tasks
from superset.moh_alerts.email_renderer import (
    csv_filename,
    render_alert_csv,
    render_alert_email,
)

ROWS: list[dict[str, Any]] = [
    {
        "org_unit_id": "F1",
        "org_unit_name": "Babare HP",
        "value": 37.5,
        "period": "201901",
    },
    {
        "org_unit_id": "F2",
        "org_unit_name": "Fite BHP",
        "value": "0.0",
        "period": "201901",
    },
    {
        "org_unit_id": "F1",
        "org_unit_name": "Babare HP",
        "value": 99,
        "period": "201901",
    },
]
EXTRA = {"facility_name_col": "org_unit_name", "metric_cols": ["value"]}


class _Record(SimpleNamespace):
    """Stand-in for a SQLAlchemy model: keeps the keyword arguments."""


class _Session:
    def __init__(self) -> None:
        self.added: list[Any] = []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    def add_all(self, objs: Any) -> None:
        self.added.extend(objs)

    def commit(self) -> None:
        pass


@pytest.fixture
def run(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Stub the database, resolver and SMTP; `state["fail"]` makes sends fail."""
    session = _Session()
    state: dict[str, Any] = {"session": session, "fail": set(), "sent": {}}

    class Recipient(_Record):
        pass

    class Facility(_Record):
        pass

    def send(to: str, **kwargs: Any) -> None:
        if to in state["fail"]:
            raise RuntimeError("550 mailbox unavailable")
        state["sent"][to] = kwargs

    stubs = {
        "_load_db": lambda: SimpleNamespace(session=session),
        "_load_models": lambda: (None, None, Recipient),
        "_load_facility_model": lambda: Facility,
        "get_moh_database": lambda database_id: object(),
        "_evaluate": lambda alert, database: [dict(row) for row in ROWS],
        "resolve": lambda *a, **k: (
            {"region_user": ["F1", "F2"], "hp_user": ["F1"]},
            0,
        ),
        "_emails_for_usernames": lambda names: {n: f"{n}@moh.test" for n in names},
        "_user_org_context": lambda *a: ("OU1", 2),
        "build_deep_link": lambda alert, org_unit: None,
        "_send_email_smtp": send,
    }
    for name, stub in stubs.items():
        monkeypatch.setattr(tasks, name, stub)
    state["Recipient"], state["Facility"] = Recipient, Facility
    return state


def _alert() -> Any:
    """An alert stand-in; typed Any because _run_delivery expects the model."""
    return SimpleNamespace(
        id=2,
        database_id=1,
        name="Drug availability",
        subject_template="[MoH] {alert_name} — {period}",
        html_extra='{"facility_name_col": "org_unit_name", "metric_cols": ["value"]}',
        dashboard_id=None,
    )


def _delivery() -> Any:
    return SimpleNamespace(id=7)


def _added(state: dict[str, Any], model: type) -> list[Any]:
    return [obj for obj in state["session"].added if isinstance(obj, model)]


def test_facility_records_keeps_name_value_and_period() -> None:
    seen = {"F1": ROWS[0], "F2": ROWS[1]}

    assert tasks.facility_records(seen, EXTRA) == [
        {
            "org_unit_id": "F1",
            "org_unit_name": "Babare HP",
            "value": 37.5,
            "period": "201901",
        },
        {
            "org_unit_id": "F2",
            "org_unit_name": "Fite BHP",
            "value": 0.0,
            "period": "201901",
        },
    ]


def test_facility_records_uses_first_metric_column_present() -> None:
    seen = {"F1": {"org_unit_id": "F1", "rate": 12, "value": 99}}

    records = tasks.facility_records(seen, {"metric_cols": ["missing", "rate"]})

    assert records[0]["value"] == 12.0


def test_facility_records_leaves_non_numeric_values_empty() -> None:
    seen = {"F1": {"org_unit_id": "F1", "value": "n/a"}, "F2": {"org_unit_id": "F2"}}

    records = tasks.facility_records(seen, {})

    assert [r["value"] for r in records] == [None, None]
    assert [r["period"] for r in records] == [None, None]


def test_run_records_alert_name_period_and_each_facility_once(
    run: dict[str, Any],
) -> None:
    delivery = _delivery()

    tasks._run_delivery(_alert(), delivery)

    assert delivery.alert_name == "Drug availability"
    assert delivery.period == "201901"
    facilities = _added(run, run["Facility"])
    assert [(f.delivery_id, f.org_unit_id, f.value) for f in facilities] == [
        (7, "F1", 37.5),
        (7, "F2", 0.0),
    ]


def test_run_records_subject_send_time_and_rows_shown(run: dict[str, Any]) -> None:
    tasks._run_delivery(_alert(), _delivery())

    by_user = {r.username: r for r in _added(run, run["Recipient"])}
    region = by_user["region_user"]
    assert region.subject == "[MoH] Drug availability — 201901"
    assert region.sent is True
    assert region.sent_at is not None
    assert region.error_message is None
    assert (region.facilities, region.facilities_shown) == (2, 2)
    assert (region.org_unit_id, region.org_unit_level) == ("OU1", 2)
    assert by_user["hp_user"].facilities == 1


def test_run_records_why_an_email_failed(run: dict[str, Any]) -> None:
    run["fail"].add("hp_user@moh.test")
    delivery = _delivery()

    tasks._run_delivery(_alert(), delivery)

    failed = next(r for r in _added(run, run["Recipient"]) if r.username == "hp_user")
    assert failed.sent is False
    assert failed.sent_at is None
    assert failed.error_message == "RuntimeError: 550 mailbox unavailable"
    assert delivery.recipients == 1


def test_run_caps_rows_shown_at_email_cap(
    run: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(tasks.current_app.config, "MOH_ALERTS_EMAIL_CAP", 1)

    tasks._run_delivery(_alert(), _delivery())

    region = next(
        r for r in _added(run, run["Recipient"]) if r.username == "region_user"
    )
    assert (region.facilities, region.facilities_shown) == (2, 1)


def test_run_attaches_full_list_only_when_over_email_cap(
    run: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(tasks.current_app.config, "MOH_ALERTS_EMAIL_CAP", 1)

    tasks._run_delivery(_alert(), _delivery())

    region = run["sent"]["region_user@moh.test"]
    assert list(region["data"]) == ["Drug_availability_201901.csv"]
    assert "full list of 2 facilities is attached" in region["html_content"]
    assert run["sent"]["hp_user@moh.test"]["data"] == {}


def test_run_attaches_nothing_when_csv_disabled(
    run: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(tasks.current_app.config, "MOH_ALERTS_EMAIL_CAP", 1)
    monkeypatch.setitem(tasks.current_app.config, "MOH_ALERTS_ATTACH_CSV", False)

    tasks._run_delivery(_alert(), _delivery())

    region = run["sent"]["region_user@moh.test"]
    assert region["data"] == {}
    assert "and 1 more</td>" in region["html_content"]


def test_csv_lists_every_row_with_excel_friendly_encoding() -> None:
    rows = [
        {**ROWS[0], "woreda": "Libokemkem", "region": "Amhara"},
        {**ROWS[1], "woreda": "ሀዋሳ", "region": "Sidama"},
    ]

    content = render_alert_csv(EXTRA, rows)

    assert content.startswith(b"\xef\xbb\xbf")
    assert content.decode("utf-8-sig").splitlines() == [
        "Facility,Woreda,Region,Value,Period,Org Unit Id",
        "Babare HP,Libokemkem,Amhara,37.5,201901,F1",
        "Fite BHP,ሀዋሳ,Sidama,0.0,201901,F2",
    ]


def test_csv_neutralises_spreadsheet_formulas_but_keeps_negative_numbers() -> None:
    rows = [{"org_unit_name": "=HYPERLINK(1)", "value": "-3.5", "change_pct": -2}]

    lines = render_alert_csv({}, rows).decode("utf-8-sig").splitlines()

    assert lines[1] == "'=HYPERLINK(1),-3.5,-2"


def test_csv_filename_is_safe() -> None:
    assert csv_filename("Drug availability / RDF", "201901") == (
        "Drug_availability_RDF_201901.csv"
    )
    assert csv_filename("Drug availability", None) == "Drug_availability.csv"
    assert csv_filename("!!!", None) == "alert.csv"


def test_email_without_attachment_keeps_plain_overflow_note() -> None:
    body = render_alert_email(_alert(), EXTRA, ROWS[:2], None, email_cap=1)

    assert "and 1 more</td>" in body
    assert "attached" not in body
