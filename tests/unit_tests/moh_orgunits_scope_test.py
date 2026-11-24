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


def test_search_requires_two_characters(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = FakeDatabase([])
    use_database(monkeypatch, database)

    response = app.test_client().get("/api/v1/moh/dhis2/organisationUnits/search?q=a")

    assert response.json == {"organisationUnits": []}
    assert database.queries == []


def test_search_is_scoped_and_returns_ancestors(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    woreda = {**ZONE, "id": "W1", "name": "Dabat", "level": 4, "level4id": "W1"}
    database = FakeDatabase([[REGION], [woreda], [REGION, ZONE]])
    use_database(monkeypatch, database)

    response = app.test_client().get(
        "/api/v1/moh/dhis2/organisationUnits/search?q=%20dab%20"
    )

    assert response.status_code == 200
    (unit,) = response.json["organisationUnits"]
    assert unit["id"] == "W1"
    assert unit["ancestors"] == [
        {"id": "R1", "displayName": "Amhara", "level": 2},
        {"id": "Z1", "displayName": "North Gondar", "level": 3},
    ]
    sql, params = database.queries[1]
    assert "level2id = :scope_id" in sql
    assert params["q"] == "dab"
    assert params["min_lvl"] == 3


def test_search_applies_cbmp_filter_per_level(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = FakeDatabase([[], []])
    use_database(monkeypatch, database)

    response = app.test_client().get(
        "/api/v1/moh/dhis2/organisationUnits/search?q=bole&cbmp_type=Hospital"
    )

    assert response.status_code == 200
    sql, params = database.queries[1]
    assert "(level = 2 AND id IN (" in sql
    assert "(level = 6 AND id IN (" in sql
    assert params["cbmp_l2_0"] == "Hospital"


# --- search: deep edge cases -------------------------------------------------

SEARCH = "/api/v1/moh/dhis2/organisationUnits/search"
WOREDA = {**ZONE, "id": "W1", "name": "Dabat", "level": 4, "level4id": "W1"}
HEALTH_POST = {
    **WOREDA,
    "id": "H1",
    "name": "Dabat HP",
    "level": 6,
    "level5id": "P1",
    "level6id": "H1",
}


def search_sql(database: FakeDatabase) -> tuple[str, dict[str, Any]]:
    """The name-search query (the one carrying the ``q`` parameter)."""
    return next(q for q in database.queries if "q" in q[1])


def test_search_requires_login(app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "current_user", SimpleNamespace(is_authenticated=False))
    database = FakeDatabase([])
    use_database(monkeypatch, database)

    assert app.test_client().get(f"{SEARCH}?q=dabat").status_code == 401
    assert database.queries == []


@pytest.mark.parametrize("query", ["", "q=", "q=%20%20%20", "q=a", "q=%20a%20"])
def test_search_ignores_blank_or_short_queries(
    app: Flask, monkeypatch: pytest.MonkeyPatch, query: str
) -> None:
    database = FakeDatabase([])
    use_database(monkeypatch, database)

    response = app.test_client().get(f"{SEARCH}?{query}")

    assert response.status_code == 200
    assert response.json == {"organisationUnits": []}
    assert database.queries == []


def test_search_route_is_not_shadowed_by_unit_lookup(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``/organisationUnits/search`` must not resolve as uid='search'."""
    database = FakeDatabase([[], []])
    use_database(monkeypatch, database)

    response = app.test_client().get(f"{SEARCH}?q=xyz")

    assert response.status_code == 200
    assert "organisationUnits" in response.json
    assert all(params.get("uid") != "search" for _, params in database.queries)


def test_search_collapses_whitespace(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = FakeDatabase([[], []])
    use_database(monkeypatch, database)

    app.test_client().get(f"{SEARCH}?q=%20north%20%20%20gondar%09")

    assert search_sql(database)[1]["q"] == "north gondar"


@pytest.mark.parametrize(
    "raw",
    ["100%", "a_b", "O'Neil", "x'); DROP TABLE org_units; --", "\\\\", "{{q}}"],
)
def test_search_passes_special_characters_only_as_bound_parameter(
    app: Flask, monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    database = FakeDatabase([[], []])
    use_database(monkeypatch, database)

    response = app.test_client().get(SEARCH, query_string={"q": raw})

    assert response.status_code == 200
    sql, params = search_sql(database)
    assert params["q"] == raw
    assert raw not in sql
    assert "positionCaseInsensitiveUTF8(name, :q)" in sql


def test_search_accepts_amharic_names(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    amharic = {**WOREDA, "name": "ደባርቅ"}
    database = FakeDatabase([[], [amharic], [REGION, ZONE]])
    use_database(monkeypatch, database)

    response = app.test_client().get(SEARCH, query_string={"q": "ደባ"})

    assert response.status_code == 200
    assert search_sql(database)[1]["q"] == "ደባ"
    assert response.json["organisationUnits"][0]["displayName"] == "ደባርቅ"


def test_search_truncates_overlong_queries(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = FakeDatabase([[], []])
    use_database(monkeypatch, database)

    app.test_client().get(SEARCH, query_string={"q": "x" * 5000})

    assert search_sql(database)[1]["q"] == "x" * api._SEARCH_MAX_CHARS


@pytest.mark.parametrize(
    ("configured", "expected"),
    [(None, 50), (10, 10), ("25", 25), ("abc", 50), (0, 1), (-5, 1)],
)
def test_search_limit_config(
    app: Flask, monkeypatch: pytest.MonkeyPatch, configured: Any, expected: int
) -> None:
    if configured is not None:
        app.config["MOH_ORG_UNITS_SEARCH_LIMIT"] = configured
    database = FakeDatabase([[], []])
    use_database(monkeypatch, database)

    app.test_client().get(f"{SEARCH}?q=dabat")

    assert f"LIMIT {expected}" in search_sql(database)[0]


def test_search_for_national_user_spans_root_to_max_level(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    national = {**REGION, "id": "ET", "level": 1, "level2id": None}
    database = FakeDatabase([[national], []])
    use_database(monkeypatch, database)

    app.test_client().get(f"{SEARCH}?q=dabat")

    sql, params = search_sql(database)
    assert ":scope_id" not in sql
    assert params["min_lvl"] == 2
    assert params["max_lvl"] == 6


def test_search_for_unassigned_user_is_unscoped(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = FakeDatabase([[], []])
    use_database(monkeypatch, database)

    app.test_client().get(f"{SEARCH}?q=dabat")

    sql, params = search_sql(database)
    assert ":scope_id" not in sql
    assert params["min_lvl"] == 2


def test_search_respects_configured_root_level(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    app.config["MOH_ORG_UNITS_ROOT_LEVEL"] = 3
    database = FakeDatabase([[], []])
    use_database(monkeypatch, database)

    app.test_client().get(f"{SEARCH}?q=dabat")

    assert search_sql(database)[1]["min_lvl"] == 3


def test_search_for_zone_user_starts_at_woredas_in_their_zone(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = FakeDatabase([[ZONE], []])
    use_database(monkeypatch, database)

    app.test_client().get(f"{SEARCH}?q=dabat")

    sql, params = search_sql(database)
    assert "level3id = :scope_id" in sql
    assert params["scope_id"] == "Z1"
    assert params["min_lvl"] == 4


def test_search_for_health_post_user_only_finds_their_own_unit(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = FakeDatabase([[HEALTH_POST], []])
    use_database(monkeypatch, database)

    app.test_client().get(f"{SEARCH}?q=dabat")

    sql, params = search_sql(database)
    assert "id = :scope_id OR level6id = :scope_id" in sql
    assert params["min_lvl"] == params["max_lvl"] == 6


def test_search_without_results_skips_ancestor_lookup(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = FakeDatabase([[], []])
    use_database(monkeypatch, database)

    response = app.test_client().get(f"{SEARCH}?q=zzz")

    assert response.json == {"organisationUnits": []}
    assert len(database.queries) == 2  # assigned-unit lookup + search


def test_search_root_level_hits_have_no_ancestors_and_no_lookup(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = FakeDatabase([[], [REGION]])
    use_database(monkeypatch, database)

    response = app.test_client().get(f"{SEARCH}?q=amh")

    assert response.json["organisationUnits"][0]["ancestors"] == []
    assert len(database.queries) == 2


def test_search_ancestors_are_deduplicated_ordered_and_trimmed(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    other_woreda = {**WOREDA, "id": "W2", "name": "Dabat Town", "level4id": "W2"}
    database = FakeDatabase(
        [
            [],
            [WOREDA, other_woreda],
            # Returned out of order and with padding, as ClickHouse may.
            [{**ZONE, "name": " North Gondar "}, {**REGION, "name": "Amhara  "}],
        ]
    )
    use_database(monkeypatch, database)

    response = app.test_client().get(f"{SEARCH}?q=dabat")

    units = response.json["organisationUnits"]
    assert [u["id"] for u in units] == ["W1", "W2"]  # DB order preserved
    for unit in units:
        assert unit["ancestors"] == [
            {"id": "R1", "displayName": "Amhara", "level": 2},
            {"id": "Z1", "displayName": "North Gondar", "level": 3},
        ]
    ancestor_params = database.queries[-1][1]
    assert sorted(ancestor_params.values()) == ["R1", "Z1"]  # no duplicates


def test_search_skips_ancestors_missing_from_table(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = FakeDatabase([[], [WOREDA], [ZONE]])  # region row missing
    use_database(monkeypatch, database)

    response = app.test_client().get(f"{SEARCH}?q=dabat")

    assert response.json["organisationUnits"][0]["ancestors"] == [
        {"id": "Z1", "displayName": "North Gondar", "level": 3}
    ]


def test_search_tolerates_null_ancestor_name(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = FakeDatabase([[], [WOREDA], [{**REGION, "name": None}, ZONE]])
    use_database(monkeypatch, database)

    response = app.test_client().get(f"{SEARCH}?q=dabat")

    assert response.status_code == 200
    assert response.json["organisationUnits"][0]["ancestors"][0]["displayName"] == ""


def test_search_cbmp_accepts_repeated_and_comma_separated_types(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = FakeDatabase([[], []])
    use_database(monkeypatch, database)

    app.test_client().get(
        f"{SEARCH}?q=dabat&cbmp_type=Hospital,Clinic&cbmp_type=Hospital&cbmp_type=%20"
    )

    sql, params = search_sql(database)
    for level in range(2, 7):
        assert f"(level = {level} AND id IN (" in sql
        assert params[f"cbmp_l{level}_0"] == "Hospital"
        assert params[f"cbmp_l{level}_1"] == "Clinic"
        assert f"cbmp_l{level}_2" not in params
    assert "AND AND" not in sql


def test_search_cbmp_combines_with_scope(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = FakeDatabase([[ZONE], []])
    use_database(monkeypatch, database)

    app.test_client().get(f"{SEARCH}?q=dabat&cbmp_type=Hospital")

    sql, params = search_sql(database)
    assert "level3id = :scope_id" in sql
    assert "(level = 2 AND" not in sql  # levels above the scope are skipped
    assert "(level = 4 AND id IN (" in sql
    assert params["scope_id"] == "Z1"


def test_search_cache_is_keyed_by_scope_cbmp_and_normalised_query(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    app.config["MOH_ORG_UNITS_CACHE_TTL"] = 60
    store: dict[str, Any] = {}
    monkeypatch.setattr(api, "_cache_get", store.get)
    monkeypatch.setattr(api, "_cache_set", store.__setitem__)
    monkeypatch.setattr(
        api,
        "_assigned_unit",
        lambda: (
            api._row_to_dhis2(SimpleNamespace(_mapping=ZONE)) | {"name": "North Gondar"}
        ),
    )
    database = FakeDatabase([[], [], []])
    use_database(monkeypatch, database)
    client = app.test_client()

    client.get(f"{SEARCH}?q=Dabat")
    client.get(f"{SEARCH}?q=%20dabat%20")  # same normalised query → cache hit
    client.get(f"{SEARCH}?q=dabat&cbmp_type=Hospital")  # different key

    assert list(store) == [
        "moh_ou:search:dabat:Z1:",
        "moh_ou:search:dabat:Z1:Hospital",
    ]
    assert len(database.queries) == 2


def test_search_cache_is_not_shared_between_scopes(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    app.config["MOH_ORG_UNITS_CACHE_TTL"] = 60
    store: dict[str, Any] = {"moh_ou:search:dabat::": {"organisationUnits": ["x"]}}
    monkeypatch.setattr(api, "_cache_get", store.get)
    monkeypatch.setattr(api, "_cache_set", store.__setitem__)
    database = FakeDatabase([[ZONE], []])
    use_database(monkeypatch, database)

    response = app.test_client().get(f"{SEARCH}?q=dabat")

    # The national-scope entry must not leak to a zone-scoped user.
    assert response.json == {"organisationUnits": []}
    assert "moh_ou:search:dabat:Z1:" in store
