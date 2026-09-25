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

REGION = {
    "id": "R1",
    "name": "Amhara",
    "level": 2,
    "level2id": "R1",
    "level3id": None,
    "level4id": None,
    "level5id": None,
    "level6id": None,
}
ZONE = {**REGION, "id": "Z1", "name": "North Gondar", "level": 3, "level3id": "Z1"}
OTHER_ZONE = {
    **REGION,
    "id": "Z9",
    "name": "Arsi",
    "level": 3,
    "level2id": "R9",
    "level3id": "Z9",
}


class FakeResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = [SimpleNamespace(_mapping=row) for row in rows]

    def all(self) -> list[SimpleNamespace]:
        return self._rows

    def first(self) -> SimpleNamespace | None:
        return self._rows[0] if self._rows else None


class FakeDatabase:
    """Records executed SQL and answers each call from ``responses`` in order."""

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
        api,
        "current_user",
        SimpleNamespace(is_authenticated=True, username="user"),
    )
    return flask_app


def use_database(monkeypatch: pytest.MonkeyPatch, database: FakeDatabase) -> None:
    monkeypatch.setattr(api, "_get_database", lambda: database)


def test_scoped_root_level_starts_below_assigned_unit() -> None:
    assert api._scoped_root_level(2, 2, 6) == 3  # region user → zones
    assert api._scoped_root_level(2, 3, 6) == 4  # zone user → woredas
    assert api._scoped_root_level(5, 2, 6) == 5  # deeper requested level wins
    assert api._scoped_root_level(2, 6, 6) == 6  # health post user → own unit


def test_is_within_scope_matches_path_segments() -> None:
    assert api._is_within_scope("/R1/Z1/W1", "Z1")
    assert api._is_within_scope("/R1/Z1", "Z1")
    assert not api._is_within_scope("/R1/Z10", "Z1")
    assert not api._is_within_scope("/R9/Z9", "Z1")


def test_region_user_gets_zones_of_their_region(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = FakeDatabase([[REGION], [ZONE]])
    use_database(monkeypatch, database)

    response = app.test_client().get("/api/v1/moh/dhis2/organisationUnits?level=2")

    assert response.status_code == 200
    assert [u["id"] for u in response.json["organisationUnits"]] == ["Z1"]
    sql, params = database.queries[-1]
    assert "level2id = :scope_id" in sql
    assert params["lvl"] == 3
    assert params["scope_id"] == "R1"


def test_national_user_gets_unscoped_roots(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    national = {**REGION, "id": "ET", "level": 1, "level2id": None}
    database = FakeDatabase([[national], [REGION]])
    use_database(monkeypatch, database)

    response = app.test_client().get("/api/v1/moh/dhis2/organisationUnits?level=2")

    assert response.status_code == 200
    sql, params = database.queries[-1]
    assert ":scope_id" not in sql
    assert params["lvl"] == 2


def test_unassigned_user_gets_unscoped_roots(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = FakeDatabase([[], [REGION]])
    use_database(monkeypatch, database)

    response = app.test_client().get("/api/v1/moh/dhis2/organisationUnits?level=2")

    assert response.status_code == 200
    assert ":scope_id" not in database.queries[-1][0]


def test_zone_user_cannot_expand_another_zone(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = FakeDatabase([[ZONE], [OTHER_ZONE]])
    use_database(monkeypatch, database)

    response = app.test_client().get("/api/v1/moh/dhis2/organisationUnits/Z9")

    assert response.status_code == 404


def test_zone_user_can_expand_own_zone(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    woreda = {**ZONE, "id": "W1", "name": "Dabat", "level": 4, "level4id": "W1"}
    database = FakeDatabase([[ZONE], [ZONE], [woreda]])
    use_database(monkeypatch, database)

    response = app.test_client().get("/api/v1/moh/dhis2/organisationUnits/Z1")

    assert response.status_code == 200
    assert [c["id"] for c in response.json["children"]] == ["W1"]


def test_me_endpoint_returns_assigned_unit(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_database(monkeypatch, FakeDatabase([[{**ZONE, "name": " North Gondar "}]]))

    response = app.test_client().get("/api/v1/moh/dhis2/me/organisationUnit")

    assert response.json == {
        "organisationUnit": {"id": "Z1", "name": "North Gondar", "level": 3}
    }
