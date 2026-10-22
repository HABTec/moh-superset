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
"""Tests for removing technical error text from JSON responses."""

from pathlib import Path

import pytest
from flask import Flask, jsonify, Response
from flask.testing import FlaskClient
from flask_babel import Babel

from superset.views.error_handling import set_app_error_handlers

TEMPLATES = Path(__file__).parents[3] / "superset" / "templates"
RAW = (
    "Error: HTTPDriver for http://127.0.0.1:8123 returned response code 408) "
    "Code: 159. DB::Exception: Timeout exceeded (TIMEOUT_EXCEEDED)"
)


@pytest.fixture
def client() -> FlaskClient:
    app = Flask(__name__, template_folder=str(TEMPLATES))
    app.config["DEBUG"] = False
    Babel(app)

    @app.route("/api/v1/chart/data", methods=["POST"])
    def chart_data() -> tuple[Response, int]:
        return jsonify({"message": RAW}), 400

    @app.route("/api/v1/async_event/")
    def async_events() -> Response:
        return jsonify({"result": [{"status": "error", "errors": [{"message": RAW}]}]})

    @app.route("/api/v1/sqllab/execute/", methods=["POST"])
    def sqllab() -> tuple[Response, int]:
        return jsonify({"message": RAW}), 400

    @app.route("/api/v1/chart/1")
    def chart() -> Response:
        return jsonify({"result": {"slice_name": "DB::Exception count by region"}})

    @app.route("/api/v1/boom")
    def boom() -> str:
        raise RuntimeError("could not connect to 10.0.0.5:5432")

    set_app_error_handlers(app)
    return app.test_client()


def test_failed_chart_data_hides_database_error(client: FlaskClient) -> None:
    response = client.post("/api/v1/chart/data")

    assert response.status_code == 400
    message = response.get_json()["message"]
    assert message.startswith("This took too long to load.")
    assert "Reference:" in message
    assert "127.0.0.1" not in response.get_data(as_text=True)


def test_async_job_errors_are_cleaned(client: FlaskClient) -> None:
    body = client.get("/api/v1/async_event/").get_data(as_text=True)

    assert "DB::Exception" not in body
    assert "Reference:" in body


def test_unexpected_exceptions_are_cleaned(client: FlaskClient) -> None:
    response = client.get("/api/v1/boom", headers={"Accept": "application/json"})

    body = response.get_data(as_text=True)
    assert response.status_code == 500
    assert "10.0.0.5" not in body
    assert "temporarily unavailable" in body


def test_sql_lab_keeps_raw_errors(client: FlaskClient) -> None:
    response = client.post("/api/v1/sqllab/execute/")

    assert response.get_json()["message"] == RAW


def test_successful_responses_are_untouched(client: FlaskClient) -> None:
    response = client.get("/api/v1/chart/1")

    assert response.get_json() == {
        "result": {"slice_name": "DB::Exception count by region"}
    }
