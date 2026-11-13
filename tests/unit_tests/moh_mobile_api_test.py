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
"""Bearer-token auth and delegation of ``superset.moh_mobile_api``."""

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from urllib.parse import quote

import jwt as pyjwt
import pytest
from flask import Flask, g, jsonify, request
from flask.testing import FlaskClient
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    JWTManager,
)
from flask_login import current_user, LoginManager
from pytest_mock import MockerFixture

from superset import moh_mobile_api, moh_orgunits_api
from superset.utils import json

JWT_SECRET = "mobile-test-secret"  # noqa: S105
MOBILE = "/api/v1/moh/mobile"
BROWSER = "/api/v1/moh/dhis2"


@dataclass
class FakeUser:
    id: int
    username: str
    is_active: bool = True

    @property
    def is_authenticated(self) -> bool:
        return True

    def get_id(self) -> str:
        return str(self.id)


USERS = {
    "1": FakeUser(1, "nurse"),
    "2": FakeUser(2, "manager"),
    "3": FakeUser(3, "retired", is_active=False),
}
UNITS = {
    "nurse": {"id": "HP1", "name": "Health Post 1", "level": 6, "path": "/ET/R1"},
    "manager": {"id": "R1", "name": "Amhara", "level": 2, "path": "/ET/R1"},
}


@pytest.fixture
def app(mocker: MockerFixture) -> Flask:
    flask_app = Flask(__name__)
    flask_app.config.update(
        SECRET_KEY="session-secret",  # noqa: S106
        JWT_SECRET_KEY=JWT_SECRET,
        # Wider than Superset's default, to prove the mobile API reads the
        # token from the Authorization header only.
        JWT_TOKEN_LOCATION=["headers", "cookies", "query_string"],
        MOH_ORG_UNITS_CACHE_TTL=0,
        PROPAGATE_EXCEPTIONS=False,
    )
    login_manager = LoginManager(flask_app)
    login_manager.user_loader(USERS.get)
    jwt_manager = JWTManager(flask_app)
    jwt_manager.user_lookup_loader(lambda _header, data: USERS.get(data["sub"]))
    flask_app.register_blueprint(moh_orgunits_api.moh_orgunits_bp)
    flask_app.register_blueprint(moh_mobile_api.moh_mobile_bp)
    # The real org-unit lookup, answered per username without a database.
    mocker.patch.object(
        moh_orgunits_api,
        "_query_assigned_unit",
        side_effect=lambda username: UNITS.get(username),
    )
    return flask_app


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


def token_for(app: Flask, uid: str, **kwargs: Any) -> str:
    with app.app_context():
        return create_access_token(identity=uid, **kwargs)


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def my_unit(client: FlaskClient, headers: dict[str, str] | None = None) -> Any:
    return client.get(f"{MOBILE}/me/organisationUnit", headers=headers or {})


# --- valid tokens -----------------------------------------------------------


def test_valid_token_returns_the_users_own_unit(
    app: Flask, client: FlaskClient
) -> None:
    response = my_unit(client, bearer(token_for(app, "1")))

    assert response.status_code == 200
    assert response.json == {
        "organisationUnit": {"id": "HP1", "name": "Health Post 1", "level": 6}
    }


def test_each_token_sees_only_its_own_scope(app: Flask, client: FlaskClient) -> None:
    nurse = my_unit(client, bearer(token_for(app, "1")))
    manager = my_unit(client, bearer(token_for(app, "2")))
    nurse_again = my_unit(client, bearer(token_for(app, "1")))

    assert nurse.json["organisationUnit"]["id"] == "HP1"
    assert manager.json["organisationUnit"]["id"] == "R1"
    assert nurse_again.json["organisationUnit"]["id"] == "HP1"


def test_user_without_assignment_gets_null_unit(
    app: Flask, client: FlaskClient
) -> None:
    USERS["4"] = FakeUser(4, "unassigned")
    try:
        response = my_unit(client, bearer(token_for(app, "4")))
    finally:
        del USERS["4"]

    assert response.status_code == 200
    assert response.json == {"organisationUnit": None}


def test_refreshed_non_fresh_access_token_is_accepted(
    app: Flask, client: FlaskClient
) -> None:
    # /api/v1/security/refresh issues non-fresh access tokens.
    response = my_unit(client, bearer(token_for(app, "1", fresh=False)))

    assert response.status_code == 200


def test_bearer_among_comma_separated_auth_values_is_accepted(
    app: Flask, client: FlaskClient
) -> None:
    headers = {"Authorization": f"Basic abc, Bearer {token_for(app, '1')}"}

    assert my_unit(client, headers).status_code == 200


def test_token_user_replaces_session_user(app: Flask, client: FlaskClient) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = "2"

    response = my_unit(client, bearer(token_for(app, "1")))

    assert response.json["organisationUnit"]["id"] == "HP1"


def test_unit_memoized_earlier_in_request_is_discarded(
    app: Flask, client: FlaskClient
) -> None:
    @app.before_request
    def memoize_other_users_unit() -> None:
        g.moh_assigned_org_unit = UNITS["manager"]

    response = my_unit(client, bearer(token_for(app, "1")))

    assert response.json["organisationUnit"]["id"] == "HP1"


def test_g_user_is_the_token_user(
    app: Flask, client: FlaskClient, mocker: MockerFixture
) -> None:
    seen: dict[str, Any] = {}

    def capture() -> Any:
        seen["g"] = g.user.username
        seen["login"] = current_user.username
        return jsonify({})

    mocker.patch.object(moh_orgunits_api, "get_latest_period", capture)
    client.get(f"{MOBILE}/latest-period", headers=bearer(token_for(app, "2")))

    assert seen == {"g": "manager", "login": "manager"}


def test_response_sets_no_cookie(app: Flask, client: FlaskClient) -> None:
    response = my_unit(client, bearer(token_for(app, "1")))

    assert response.status_code == 200
    assert "Set-Cookie" not in response.headers


# --- rejected requests ------------------------------------------------------


def assert_unauthorized(response: Any) -> None:
    assert response.status_code == 401
    assert response.is_json
    assert "message" in response.json


def test_missing_header_is_rejected(client: FlaskClient) -> None:
    assert_unauthorized(my_unit(client))


@pytest.mark.parametrize(
    "value",
    [
        "",
        "Bearer",
        "Bearer ",
        "bearer {token}",
        "BEARER {token}",
        "Token {token}",
        "Basic {token}",
        "{token}",
        "Bearer {token} extra",
        "Bearer {token}, Bearer {token}",
    ],
)
def test_malformed_authorization_header_is_rejected(
    app: Flask, client: FlaskClient, value: str
) -> None:
    header = value.format(token=token_for(app, "1"))

    assert_unauthorized(my_unit(client, {"Authorization": header}))


def test_garbage_token_is_rejected(client: FlaskClient) -> None:
    assert_unauthorized(my_unit(client, bearer("not.a.jwt")))


def test_expired_token_is_rejected(app: Flask, client: FlaskClient) -> None:
    token = token_for(app, "1", expires_delta=timedelta(seconds=-1))

    assert_unauthorized(my_unit(client, bearer(token)))


def test_token_signed_with_another_secret_is_rejected(
    app: Flask, client: FlaskClient
) -> None:
    payload = pyjwt.decode(token_for(app, "1"), JWT_SECRET, algorithms=["HS256"])
    forged = pyjwt.encode(payload, "attacker-secret", algorithm="HS256")

    assert_unauthorized(my_unit(client, bearer(forged)))


def test_unsigned_token_is_rejected(app: Flask, client: FlaskClient) -> None:
    payload = pyjwt.decode(token_for(app, "1"), JWT_SECRET, algorithms=["HS256"])
    unsigned = pyjwt.encode(payload, None, algorithm="none")

    assert_unauthorized(my_unit(client, bearer(unsigned)))


def test_token_with_swapped_user_is_rejected(app: Flask, client: FlaskClient) -> None:
    header, _payload, signature = token_for(app, "1").split(".")
    _, other_payload, _ = token_for(app, "2").split(".")

    tampered = f"{header}.{other_payload}.{signature}"

    assert_unauthorized(my_unit(client, bearer(tampered)))


def test_refresh_token_cannot_be_used_as_access_token(
    app: Flask, client: FlaskClient
) -> None:
    with app.app_context():
        refresh = create_refresh_token(identity="1")

    assert_unauthorized(my_unit(client, bearer(refresh)))


def test_token_for_unknown_user_is_rejected(app: Flask, client: FlaskClient) -> None:
    assert_unauthorized(my_unit(client, bearer(token_for(app, "999"))))


def test_token_for_inactive_user_is_rejected(app: Flask, client: FlaskClient) -> None:
    assert_unauthorized(my_unit(client, bearer(token_for(app, "3"))))


def test_token_in_query_string_is_ignored(app: Flask, client: FlaskClient) -> None:
    token = token_for(app, "1")

    response = client.get(f"{MOBILE}/me/organisationUnit?jwt={token}")

    assert_unauthorized(response)


def test_token_in_cookie_is_ignored(app: Flask, client: FlaskClient) -> None:
    client.set_cookie("access_token_cookie", token_for(app, "1"))

    assert_unauthorized(my_unit(client))


def test_browser_session_alone_is_not_enough(client: FlaskClient) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = "1"

    assert_unauthorized(my_unit(client))


def test_rejection_does_not_reach_the_endpoint(
    client: FlaskClient, mocker: MockerFixture
) -> None:
    endpoint = mocker.patch.object(moh_orgunits_api, "get_tab_context")

    client.get(f"{MOBILE}/tab-context", headers=bearer("bad"))

    endpoint.assert_not_called()


def test_rejection_log_does_not_contain_the_token(
    client: FlaskClient, caplog: pytest.LogCaptureFixture
) -> None:
    secret_looking = "eyJhbGciOiJIUzI1NiJ9.c2VjcmV0.c2lnbmF0dXJl"  # noqa: S105

    with caplog.at_level(logging.INFO, logger=moh_mobile_api.__name__):
        my_unit(client, bearer(secret_looking))

    assert "Mobile API token rejected" in caplog.text
    assert secret_looking not in caplog.text


def test_failed_request_does_not_leak_user_into_next_request(
    app: Flask, client: FlaskClient
) -> None:
    assert my_unit(client, bearer(token_for(app, "1"))).status_code == 200

    assert_unauthorized(my_unit(client))


# --- routing and delegation -------------------------------------------------


@pytest.mark.parametrize(
    ("path", "function", "args"),
    [
        ("/organisationUnits?level=3", "list_units", ()),
        ("/organisationUnits/R1", "get_unit", ("R1",)),
        ("/me/organisationUnit", "get_my_unit", ()),
        ("/latest-period", "get_latest_period", ()),
        ("/data-freshness", "get_data_freshness", ()),
        ("/tab-context?q=%7B%7D", "get_tab_context", ()),
    ],
)
def test_each_route_delegates_to_the_original_endpoint(
    app: Flask,
    client: FlaskClient,
    mocker: MockerFixture,
    path: str,
    function: str,
    args: tuple[str, ...],
) -> None:
    seen: dict[str, Any] = {}

    def original(*call_args: str) -> Any:
        seen["args"] = call_args
        seen["query"] = request.query_string.decode()
        return jsonify({"from": function})

    mocker.patch.object(moh_orgunits_api, function, original)

    response = client.get(f"{MOBILE}{path}", headers=bearer(token_for(app, "1")))

    assert response.status_code == 200
    assert response.json == {"from": function}
    assert seen["args"] == args
    assert seen["query"] == path.partition("?")[2]


def test_tab_context_json_reaches_original_endpoint(
    app: Flask, client: FlaskClient, mocker: MockerFixture
) -> None:
    build = mocker.patch.object(
        moh_orgunits_api, "_build_tab_context", return_value={"sources": []}
    )
    q = '{"dashboardId": 12, "tabPath": ["ANC"], "fiscalYears": ["2018"]}'

    response = client.get(
        f"{MOBILE}/tab-context?q={quote(q)}", headers=bearer(token_for(app, "1"))
    )

    assert response.status_code == 200
    assert response.json == {"sources": []}
    context_request = build.call_args.args[0]
    assert context_request.dashboard_id == 12
    assert context_request.tab_path == ["ANC"]
    assert context_request.fiscal_years == ["2018"]


def test_tab_context_invalid_json_keeps_original_400(
    app: Flask, client: FlaskClient
) -> None:
    response = client.get(
        f"{MOBILE}/tab-context?q=not-json", headers=bearer(token_for(app, "1"))
    )

    assert response.status_code == 400


@pytest.mark.parametrize("dashboard_id", [[1], {"a": 1}])
def test_tab_context_unhashable_dashboard_id_is_400(
    app: Flask, client: FlaskClient, dashboard_id: object
) -> None:
    q = quote(json.dumps({"dashboardId": dashboard_id}))

    response = client.get(
        f"{MOBILE}/tab-context?q={q}", headers=bearer(token_for(app, "1"))
    )

    assert response.status_code == 400
    assert response.json == {"message": "dashboardId must be a number or string"}


@pytest.mark.parametrize("q", ["[]", '"x"', "123", "null", "{}"])
def test_tab_context_non_object_q_is_passed_through(
    app: Flask, client: FlaskClient, mocker: MockerFixture, q: str
) -> None:
    original = mocker.patch.object(
        moh_orgunits_api, "get_tab_context", return_value=jsonify({})
    )

    client.get(
        f"{MOBILE}/tab-context?q={quote(q)}", headers=bearer(token_for(app, "1"))
    )

    original.assert_called_once()


def test_invalid_level_keeps_original_400(app: Flask, client: FlaskClient) -> None:
    response = client.get(
        f"{MOBILE}/organisationUnits?level=99", headers=bearer(token_for(app, "1"))
    )

    assert response.status_code == 400


def test_endpoint_error_is_not_turned_into_401(
    app: Flask, client: FlaskClient, mocker: MockerFixture
) -> None:
    mocker.patch.object(
        moh_orgunits_api, "get_data_freshness", side_effect=RuntimeError("db down")
    )

    response = client.get(
        f"{MOBILE}/data-freshness", headers=bearer(token_for(app, "1"))
    )

    assert response.status_code == 500


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_write_methods_are_not_allowed(
    app: Flask, client: FlaskClient, method: str
) -> None:
    response = getattr(client, method)(
        f"{MOBILE}/tab-context", headers=bearer(token_for(app, "1"))
    )

    assert response.status_code == 405


def test_unknown_path_is_404(app: Flask, client: FlaskClient) -> None:
    response = client.get(f"{MOBILE}/nope", headers=bearer(token_for(app, "1")))

    assert response.status_code == 404


def test_browser_test_page_is_not_exposed(app: Flask, client: FlaskClient) -> None:
    response = client.get(f"{MOBILE}/test", headers=bearer(token_for(app, "1")))

    assert response.status_code == 404


# --- existing browser API is unchanged --------------------------------------


def test_browser_api_still_rejects_bearer_tokens(
    app: Flask, client: FlaskClient
) -> None:
    response = client.get(
        f"{BROWSER}/me/organisationUnit", headers=bearer(token_for(app, "1"))
    )

    assert response.status_code == 401


def test_browser_api_still_accepts_session(client: FlaskClient) -> None:
    with client.session_transaction() as session:
        session["_user_id"] = "2"

    response = client.get(f"{BROWSER}/me/organisationUnit")

    assert response.status_code == 200
    assert response.json["organisationUnit"]["id"] == "R1"
