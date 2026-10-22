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
"""Tests for replacing technical error text with user-facing messages."""

from collections.abc import Iterator

import pytest
from flask import Flask
from flask_babel import Babel

from superset.utils.error_sanitizer import (
    classify,
    ErrorSanitizer,
    is_technical,
    sanitize_errors,
)

CLICKHOUSE_TIMEOUT = (
    "Error: HTTPDriver for http://127.0.0.1:8123 returned response code 408) "
    "Code: 159. DB::Exception: Timeout exceeded: elapsed 65623.834 ms, "
    "maximum: 60000.000 ms. (TIMEOUT_EXCEEDED)"
)


@pytest.fixture(autouse=True)
def app_context() -> Iterator[None]:
    app = Flask(__name__)
    Babel(app)
    with app.app_context():
        yield


@pytest.mark.parametrize(
    "message,kind",
    [
        (CLICKHOUSE_TIMEOUT, "timeout"),
        (
            "psycopg2.errors.QueryCanceled: canceling statement due to "
            "statement timeout",
            "timeout",
        ),
        (
            "DB::Exception: Memory limit exceeded. (MEMORY_LIMIT_EXCEEDED)",
            "too_much_data",
        ),
        (
            "psycopg2.OperationalError: could not connect to server: "
            "Connection refused",
            "unavailable",
        ),
        ("Code: 497. DB::Exception: ACCESS_DENIED", "access"),
        (
            "Code: 47. DB::Exception: Missing columns: 'woreda' (UNKNOWN_IDENTIFIER)",
            "setup",
        ),
        ("KeyError: 'metrics'", "generic"),
    ],
)
def test_classifies_raw_errors(message: str, kind: str) -> None:
    assert is_technical(message)
    assert classify(message) == kind


@pytest.mark.parametrize(
    "message",
    [
        "Chart not found",
        "You don't have access to this chart.",
        "Error: Columns missing in dataset: region",
        "Name must be unique",
    ],
)
def test_keeps_user_facing_messages(message: str) -> None:
    assert not is_technical(message)
    sanitizer = ErrorSanitizer()
    assert sanitizer.message(message) == message
    assert not sanitizer.changed


def test_replaces_raw_message_without_leaking_details() -> None:
    sanitizer = ErrorSanitizer()
    cleaned = sanitizer.sanitize({"message": CLICKHOUSE_TIMEOUT})

    assert sanitizer.changed
    message = cleaned["message"]
    assert message.startswith("This took too long to load.")
    assert f"(Reference: {sanitizer.reference})" in message
    for detail in ("127.0.0.1", "8123", "DB::", "Code: 159", "HTTPDriver", "60000"):
        assert detail not in message


def test_logs_original_with_reference(caplog: pytest.LogCaptureFixture) -> None:
    sanitizer = ErrorSanitizer(context="/api/v1/chart/data")
    sanitizer.sanitize({"message": CLICKHOUSE_TIMEOUT})

    assert sanitizer.reference in caplog.text
    assert "127.0.0.1:8123" in caplog.text


def test_superset_error_objects_are_cleaned() -> None:
    sanitizer = ErrorSanitizer()
    cleaned = sanitizer.sanitize(
        {
            "errors": [
                {
                    "message": "could not reach the server",
                    "error_type": "GENERIC_DB_ENGINE_ERROR",
                    "level": "error",
                    "extra": {"engine_name": "ClickHouse", "issue_codes": [1002]},
                }
            ],
            "stacktrace": "Traceback (most recent call last): ...",
        }
    )

    error = cleaned["errors"][0]
    assert "Reference:" in error["message"]
    assert error["extra"] == {"issue_codes": [1002]}
    assert "stacktrace" not in cleaned


def test_nested_validation_messages_are_untouched() -> None:
    payload = {"message": {"slice_name": ["Missing data for required field."]}}
    sanitizer = ErrorSanitizer()

    assert sanitizer.sanitize(payload) == payload
    assert not sanitizer.changed


def test_one_reference_per_payload() -> None:
    sanitizer = ErrorSanitizer()
    cleaned = sanitizer.sanitize(
        {"error": CLICKHOUSE_TIMEOUT, "errors": [{"message": "KeyError: 'x'"}]}
    )

    assert sanitizer.reference in cleaned["error"]
    assert sanitizer.reference in cleaned["errors"][0]["message"]


def test_sanitize_errors_for_async_jobs() -> None:
    cleaned = sanitize_errors([{"message": CLICKHOUSE_TIMEOUT}])

    assert "127.0.0.1" not in cleaned[0]["message"]
