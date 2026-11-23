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
"""Tests for the per-alert highest notified level (``min_recipient_level``)."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, Iterator

import pytest
from flask import Flask

from superset.moh_alerts import tasks, views
from superset.moh_alerts.recipient_resolver import (
    get_ancestor_map,
    min_recipient_level,
    resolve,
)

NATIONAL, CITY, BOLE, YEKA = "FMOH", "ADDIS", "BOLE", "YEKA"
HOSP1, HOSP2, CITY_HOSP, PHCU = "HOSP1", "HOSP2", "CITYHOSP", "PHCU1"

# National > city > sub-cities > hospitals, plus a city-administered hospital
# directly under the city and a health centre one level deeper.
ORG_UNITS: dict[str, dict[str, Any]] = {
    NATIONAL: {"id": NATIONAL, "level1id": NATIONAL},
    CITY: {"id": CITY, "level1id": NATIONAL, "level2id": CITY},
    HOSP1: {
        "id": HOSP1,
        "level1id": NATIONAL,
        "level2id": CITY,
        "level3id": BOLE,
        "level4id": HOSP1,
    },
    HOSP2: {
        "id": HOSP2,
        "level1id": NATIONAL,
        "level2id": CITY,
        "level3id": YEKA,
        "level4id": HOSP2,
    },
    CITY_HOSP: {
        "id": CITY_HOSP,
        "level1id": NATIONAL,
        "level2id": CITY,
        "level3id": CITY_HOSP,
        "level4id": None,
    },
    PHCU: {
        "id": PHCU,
        "level1id": NATIONAL,
        "level2id": CITY,
        "level3id": BOLE,
        "level4id": HOSP1,
        "level5id": PHCU,
    },
}

USERS: dict[str, list[str]] = {
    NATIONAL: ["national_user", "both_levels_user"],
    CITY: ["city_user", "both_levels_user"],
    BOLE: ["bole_user"],
    YEKA: ["yeka_user"],
    HOSP1: ["hosp1_user"],
    HOSP2: ["hosp2_user"],
    CITY_HOSP: ["city_hosp_user"],
}


class _Result:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> list[dict[str, Any]]:
        return self._rows


class _Database:
    """Answers the two resolver queries from the dictionaries above."""

    def __init__(self) -> None:
        self.queries: list[dict[str, Any]] = []

    @contextmanager
    def get_sqla_engine(self) -> Iterator[Any]:
        yield self

    @contextmanager
    def connect(self) -> Iterator[Any]:
        yield self

    def execute(self, statement: Any, params: dict[str, Any]) -> _Result:
        self.queries.append(params)
        if "org_unit_id, username" in str(statement):
            return _Result(
                [
                    {"org_unit_id": unit, "username": name}
                    for unit in params["units"]
                    for name in USERS.get(unit, [])
                ]
            )
        return _Result([ORG_UNITS[i] for i in params["ids"] if i in ORG_UNITS])


def _resolve(
    facilities: list[str], min_level: int = 1, **kwargs: Any
) -> tuple[dict[str, list[str]], int]:
    return resolve(
        _Database(),  # type: ignore[arg-type]
        facilities,
        min_level=min_level,
        **kwargs,
    )


def test_every_level_is_notified_by_default() -> None:
    per_user, ignored = _resolve([HOSP1])
    assert ignored == 0
    assert set(per_user) == {
        "national_user",
        "both_levels_user",
        "city_user",
        "bole_user",
        "hosp1_user",
    }


def test_level_one_is_the_same_as_no_setting() -> None:
    assert _resolve([HOSP1, HOSP2], min_level=1) == resolve(
        _Database(),  # type: ignore[arg-type]
        [HOSP1, HOSP2],
    )


def test_level_two_leaves_out_national_users_only() -> None:
    per_user, ignored = _resolve([HOSP1], min_level=2)
    assert ignored == 0
    assert per_user == {
        "both_levels_user": [HOSP1],
        "city_user": [HOSP1],
        "bole_user": [HOSP1],
        "hosp1_user": [HOSP1],
    }


def test_user_also_mapped_to_the_city_is_still_notified_through_it() -> None:
    per_user, _ = _resolve([HOSP1, HOSP2], min_level=2)
    assert per_user["both_levels_user"] == [HOSP1, HOSP2]
    assert "national_user" not in per_user


def test_each_user_still_gets_only_their_own_facilities() -> None:
    per_user, _ = _resolve([HOSP1, HOSP2, CITY_HOSP], min_level=2)
    assert per_user == {
        "both_levels_user": [CITY_HOSP, HOSP1, HOSP2],
        "city_user": [CITY_HOSP, HOSP1, HOSP2],
        "bole_user": [HOSP1],
        "yeka_user": [HOSP2],
        "hosp1_user": [HOSP1],
        "hosp2_user": [HOSP2],
        "city_hosp_user": [CITY_HOSP],
    }


def test_city_administered_hospital_with_empty_lower_levels() -> None:
    per_user, _ = _resolve([CITY_HOSP], min_level=2)
    assert set(per_user) == {"both_levels_user", "city_user", "city_hosp_user"}


def test_health_centre_below_a_hospital_reaches_the_hospital_users() -> None:
    per_user, _ = _resolve([PHCU], min_level=2)
    assert set(per_user) == {
        "both_levels_user",
        "city_user",
        "bole_user",
        "hosp1_user",
    }


def test_level_three_also_leaves_out_city_users() -> None:
    per_user, _ = _resolve([HOSP1, CITY_HOSP], min_level=3)
    assert per_user == {
        "bole_user": [HOSP1],
        "hosp1_user": [HOSP1],
        "city_hosp_user": [CITY_HOSP],
    }


def test_flagged_unit_above_the_cut_still_notifies_its_own_users() -> None:
    # The facility itself is always in its chain, even at level 1
    per_user, _ = _resolve([NATIONAL], min_level=2)
    assert per_user == {
        "national_user": [NATIONAL],
        "both_levels_user": [NATIONAL],
    }


def test_highest_level_keeps_only_the_facility_itself() -> None:
    chain = get_ancestor_map(
        _Database(),  # type: ignore[arg-type]
        [HOSP1, CITY_HOSP],
        "moh",
        "org_units",
        min_level=7,
    )
    assert chain == {HOSP1: {HOSP1}, CITY_HOSP: {CITY_HOSP}}


@pytest.mark.parametrize("level", [0, -5])
def test_level_below_one_notifies_every_level(level: int) -> None:
    assert _resolve([HOSP1], min_level=level) == _resolve([HOSP1], min_level=1)


def test_unknown_facility_is_counted_as_ignored() -> None:
    per_user, ignored = _resolve([HOSP1, "MISSING"], min_level=2)
    assert ignored == 1
    assert per_user["hosp1_user"] == [HOSP1]
    assert all("MISSING" not in facilities for facilities in per_user.values())


def test_no_facilities_gives_no_recipients_and_no_queries() -> None:
    database = _Database()
    assert resolve(database, [], min_level=2) == ({}, 0)  # type: ignore[arg-type]
    assert database.queries == []


def test_duplicate_facility_ids_are_counted_once() -> None:
    per_user, ignored = _resolve([HOSP1, HOSP1, HOSP1], min_level=2)
    assert ignored == 0
    assert per_user["city_user"] == [HOSP1]


def test_small_query_chunks_give_the_same_result() -> None:
    facilities = [HOSP1, HOSP2, CITY_HOSP, PHCU]
    assert _resolve(facilities, min_level=2, max_per_query=1) == _resolve(
        facilities, min_level=2
    )


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        ({}, 1),
        ({"other": "setting"}, 1),
        ({"min_recipient_level": 1}, 1),
        ({"min_recipient_level": 2}, 2),
        ({"min_recipient_level": 7}, 7),
        ({"min_recipient_level": "3"}, 3),
        ({"min_recipient_level": " 2 "}, 2),
        ({"min_recipient_level": 2.0}, 2),
        ({"min_recipient_level": 2.9}, 2),
        ({"min_recipient_level": "2.5"}, 1),
        ({"min_recipient_level": ""}, 1),
        ({"min_recipient_level": 0}, 1),
        ({"min_recipient_level": -3}, 1),
        ({"min_recipient_level": 99}, 7),
        ({"min_recipient_level": "national"}, 1),
        ({"min_recipient_level": None}, 1),
        ({"min_recipient_level": True}, 1),
        ({"min_recipient_level": False}, 1),
        ({"min_recipient_level": [2]}, 1),
        ({"min_recipient_level": {"level": 2}}, 1),
        ({"min_recipient_level": float("inf")}, 1),
        ({"min_recipient_level": float("nan")}, 1),
        ([], 1),
        ("min_recipient_level", 1),
        (None, 1),
    ],
)
def test_min_recipient_level_reads_html_extra(extra: Any, expected: int) -> None:
    assert min_recipient_level(extra) == expected


def _capture_resolve(
    monkeypatch: pytest.MonkeyPatch, target: Any, name: str
) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def fake_resolve(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], int]:
        captured.update(kwargs, facilities=list(args[1]))
        return {}, 0

    monkeypatch.setattr(target, name, fake_resolve)
    return captured


@pytest.mark.parametrize(
    ("html_extra", "expected"),
    [
        ('{"min_recipient_level": 2}', 2),
        ('{"metric_cols": ["value"]}', 1),
        (None, 1),
        ("not json", 1),
    ],
)
def test_scheduled_runs_and_retries_apply_the_alert_setting(
    monkeypatch: pytest.MonkeyPatch, html_extra: str | None, expected: int
) -> None:
    captured = _capture_resolve(monkeypatch, tasks, "resolve")
    monkeypatch.setattr(
        tasks,
        "_evaluate",
        lambda alert, database: [{"org_unit_id": HOSP1}, {"org_unit_id": None}],
    )
    alert = SimpleNamespace(id=1, html_extra=html_extra)
    with Flask(__name__).app_context():
        seen, _, ignored = tasks._resolve_targets(alert, object())  # type: ignore[arg-type]
    assert captured["min_level"] == expected
    assert captured["facilities"] == [HOSP1]
    assert list(seen) == [HOSP1]
    assert ignored == 1


@pytest.mark.parametrize(
    ("html_extra", "expected"),
    [('{"min_recipient_level": 2}', 2), ("{}", 1), (None, 1)],
)
def test_test_button_applies_the_alert_setting(
    monkeypatch: pytest.MonkeyPatch, html_extra: str | None, expected: int
) -> None:
    alert = SimpleNamespace(id=5, database_id=1, html_extra=html_extra, sql_query="x")
    session = SimpleNamespace(
        get=lambda model, alert_id: alert,
        query=lambda model: SimpleNamespace(all=lambda: []),
    )
    captured: dict[str, Any] = {}
    rendered: dict[str, Any] = {}

    class _AlertDatabase(_Database):
        def execute(self, statement: Any, params: Any = None) -> _Result:
            return _Result([{"org_unit_id": HOSP1}])

    def fake_resolve(*args: Any, **kwargs: Any) -> tuple[dict[str, Any], int]:
        captured.update(kwargs)
        return {"city_user": [HOSP1]}, 0

    def fake_render(name: str, **context: Any) -> str:
        rendered.update(context)
        return "ok"

    database = _AlertDatabase()
    monkeypatch.setattr(views, "_require_admin", lambda: True)
    monkeypatch.setattr(views, "_load_db", lambda: SimpleNamespace(session=session))
    monkeypatch.setattr(views, "_load_models", lambda: (object, None, None))
    monkeypatch.setattr(views, "_load_database_model", lambda: object)
    monkeypatch.setattr(views, "get_moh_database", lambda database_id: database)
    monkeypatch.setattr(views, "_load_resolve", lambda: fake_resolve)
    monkeypatch.setattr(views, "render_template", fake_render)
    with Flask(__name__).test_request_context(method="POST"):
        views.test(alert.id)
    assert "error" not in rendered["test"], rendered["test"]
    assert captured["min_level"] == expected
    assert rendered["test"]["recipients"] == {"city_user": 1}
