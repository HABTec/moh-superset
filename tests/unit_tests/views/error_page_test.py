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
"""Tests for the shared HTML error page."""

from pathlib import Path

import pytest
from flask import abort, Flask
from flask.testing import FlaskClient
from flask_babel import Babel
from sqlalchemy import exc

from superset.errors import ErrorLevel, SupersetError, SupersetErrorType
from superset.exceptions import SupersetErrorException
from superset.views.error_handling import set_app_error_handlers

BROWSER_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
TEMPLATES = Path(__file__).parents[3] / "superset" / "templates"


@pytest.fixture
def client() -> FlaskClient:
    app = Flask(__name__, template_folder=str(TEMPLATES))
    app.config["DEBUG"] = False
    Babel(app)

    @app.route("/db")
    def db_error() -> str:
        raise exc.OperationalError("SELECT 1", {}, Exception("connection refused"))

    @app.route("/boom")
    def server_error() -> str:
        raise RuntimeError("secret internal detail")

    @app.route("/denied")
    def denied() -> str:
        abort(403)

    @app.route("/conn")
    def connection_error() -> str:
        raise SupersetErrorException(
            SupersetError(
                message="host down",
                error_type=SupersetErrorType.CONNECTION_HOST_DOWN_ERROR,
                level=ErrorLevel.ERROR,
            )
        )

    @app.route("/api/v1/boom")
    def api_error() -> str:
        raise RuntimeError("api failure")

    set_app_error_handlers(app)
    return app.test_client()


@pytest.mark.parametrize(
    "path, status, title",
    [
        ("/db", 503, "We can&#39;t reach the database right now"),
        ("/conn", 503, "We can&#39;t reach the database right now"),
        ("/boom", 500, "Something went wrong on our side"),
        ("/denied", 403, "You don&#39;t have access to this page"),
        ("/missing", 404, "We couldn&#39;t find that page"),
    ],
)
def test_browser_gets_error_page(
    client: FlaskClient, path: str, status: int, title: str
) -> None:
    response = client.get(path, headers={"Accept": BROWSER_ACCEPT})
    body = response.get_data(as_text=True)
    assert response.status_code == status
    assert response.mimetype == "text/html"
    assert title in body
    assert "secret internal detail" not in body


def test_fetch_and_api_calls_get_json(client: FlaskClient) -> None:
    for path, accept in [("/boom", "*/*"), ("/api/v1/boom", BROWSER_ACCEPT)]:
        response = client.get(path, headers={"Accept": accept})
        assert response.status_code == 500
        assert response.is_json
