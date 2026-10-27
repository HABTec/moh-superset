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
"""
Replace technical error text with plain-language messages before it reaches
users.

Database drivers, Python exceptions and HTTP clients produce messages that
expose internal hosts, ports, engine names, error codes and SQL. Any such
message leaving the server is swapped for a friendly message of the matching
kind (timeout, too much data, unavailable, setup problem, or generic) followed
by a short reference. The original text is logged with that reference so
administrators can still find the exact cause.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from flask_babel import gettext as __

logger = logging.getLogger(__name__)

# Signs that a message was written for developers rather than users.
TECHNICAL_MARKERS = re.compile(
    r"Traceback|\bDB::|\bCode:\s*\d+|https?://|\b\d{1,3}(?:\.\d{1,3}){3}\b"
    r"|\blocalhost:\d+|\b\w+(?:Exception|Error)\b(?:\s*[:(]|$)"
    r"|\bpsycopg|\bsqlalchemy|\bclickhouse|\bHTTPDriver|\bpymysql|\bpyodbc"
    r"|\bErrno\b|\bline \d+|\.py\b|object has no attribute|NoneType"
    r"|\(Background on this error|\bSELECT\s.+\sFROM\s|\belapsed\b.*\bms\b",
    re.IGNORECASE | re.DOTALL,
)

# Ordered: the first matching kind wins.
ERROR_KINDS: list[tuple[str, re.Pattern[str]]] = [
    (
        "timeout",
        re.compile(
            r"time ?out|timed out|TIMEOUT_EXCEEDED|Code:\s*159\b|statement timeout"
            r"|canceling statement|SoftTimeLimitExceeded|\b(?:408|504)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "too_much_data",
        re.compile(
            r"MEMORY_LIMIT_EXCEEDED|Code:\s*(?:241|396)\b|TOO_MANY_ROWS"
            r"|out of memory|memory limit|too many rows|result set too large",
            re.IGNORECASE,
        ),
    ),
    (
        "unavailable",
        re.compile(
            r"connection refused|could not connect|connection reset"
            r"|server closed the connection|name or service not known"
            r"|network is unreachable|no route to host|NETWORK_ERROR"
            r"|Code:\s*210\b|Max retries exceeded|\b(?:502|503)\b"
            r"|could not translate host name|ConnectionError",
            re.IGNORECASE,
        ),
    ),
    (
        "access",
        re.compile(
            r"permission denied|access denied|ACCESS_DENIED|Code:\s*497\b"
            r"|authentication failed|not authorized|insufficient privilege",
            re.IGNORECASE,
        ),
    ),
    (
        "setup",
        re.compile(
            r"UNKNOWN_(?:IDENTIFIER|TABLE|FUNCTION)|SYNTAX_ERROR|NOT_AN_AGGREGATE"
            r"|ILLEGAL_TYPE|Code:\s*(?:43|46|47|60|62|81|215|386)\b|syntax error"
            r"|does not exist|no such (?:table|column)|unknown (?:column|table)"
            r"|undefined (?:column|table)|missing columns|ProgrammingError"
            r"|missing in dataset",
            re.IGNORECASE,
        ),
    ),
]


def _friendly_messages() -> dict[str, str]:
    # Built lazily so translations resolve within a request context.
    return {
        "timeout": __(
            "This took too long to load. Try narrowing the filters (for "
            "example fewer org units or a shorter period), then try again."
        ),
        "too_much_data": __(
            "This asks for too much data at once. Narrow the filters and try again."
        ),
        "unavailable": __(
            "The data source is temporarily unavailable. Please try again in a "
            "few minutes."
        ),
        "access": __(
            "You don't have access to this data. Ask your administrator if you need it."
        ),
        "setup": __(
            "This can't be loaded because of a setup problem. Please contact "
            "your dashboard administrator."
        ),
        "generic": __("Something went wrong while loading this."),
    }


# Keys whose string values are user-facing error text.
MESSAGE_KEYS = {"message", "error", "error_message", "msg", "errorMessage"}
# Keys that only carry debugging detail and are dropped outright.
DROPPED_KEYS = {"stacktrace", "stack_trace", "stackTrace", "traceback"}
# SupersetError ``extra`` keys that reveal internals.
DROPPED_EXTRA_KEYS = {"engine_name", "sql", "query", "host", "port"}
# Superset error types that always carry raw driver text.
RAW_ERROR_TYPES = {"GENERIC_DB_ENGINE_ERROR", "GENERIC_BACKEND_ERROR"}


def is_technical(message: str) -> bool:
    """Whether a message contains developer-facing detail."""
    return bool(TECHNICAL_MARKERS.search(message))


def classify(message: str) -> str:
    """The kind of failure a raw error message describes."""
    for kind, pattern in ERROR_KINDS:
        if pattern.search(message):
            return kind
    return "generic"


def new_reference() -> str:
    return uuid.uuid4().hex[:8].upper()


def friendly_message(raw: str, reference: str) -> str:
    """Plain-language replacement for ``raw``, ending with ``reference``."""
    message = _friendly_messages()[classify(raw)]
    return __("%(message)s (Reference: %(ref)s)", message=message, ref=reference)


class ErrorSanitizer:
    """
    Walks a JSON-like payload replacing technical error text in place. One
    reference is shared by every replacement in the payload, so a single
    response maps to a single log entry.
    """

    def __init__(self, context: str = "") -> None:
        self.context = context
        self.reference = new_reference()
        self.changed = False

    def _replace(self, raw: str) -> str:
        self.changed = True
        logger.warning(
            "Sanitized error ref=%s context=%s original=%s",
            self.reference,
            self.context,
            raw,
        )
        return friendly_message(raw, self.reference)

    def message(self, raw: str, force: bool = False) -> str:
        if force or is_technical(raw):
            return self._replace(raw)
        return raw

    def sanitize(self, payload: Any) -> Any:
        if isinstance(payload, list):
            return [self.sanitize(item) for item in payload]
        if not isinstance(payload, dict):
            return payload

        force = payload.get("error_type") in RAW_ERROR_TYPES
        result: dict[str, Any] = {}
        for key, value in payload.items():
            if key in DROPPED_KEYS:
                self.changed = True
                continue
            if key in MESSAGE_KEYS and isinstance(value, str):
                result[key] = self.message(value, force=force)
            elif key == "extra" and isinstance(value, dict) and "error_type" in payload:
                cleaned = {
                    k: v for k, v in value.items() if k not in DROPPED_EXTRA_KEYS
                }
                self.changed = self.changed or len(cleaned) != len(value)
                result[key] = self.sanitize(cleaned)
            else:
                result[key] = self.sanitize(value)
        return result


def sanitize_errors(errors: Any, context: str = "") -> Any:
    """Sanitize a standalone error payload (e.g. async job errors)."""
    return ErrorSanitizer(context).sanitize(errors)
