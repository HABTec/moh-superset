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
"""Readable descriptions of alert email failures, and how each is handled.

The prefixes are stored in ``moh_alert_delivery_recipient.error_message`` and
are also how later runs recognise rejected addresses and emails awaiting a
retry, so changing one orphans rows written with the old text.
"""

from __future__ import annotations

import re
import smtplib
from enum import Enum
from typing import NamedTuple

INVALID_ADDRESS_PREFIX = "Invalid email address: "
RETRY_PREFIX = "Retrying later: "
GAVE_UP_PREFIX = "Not delivered after retries: "

SENDING_DEFERRED_MESSAGE = (
    f"{RETRY_PREFIX}sending stopped for this run after repeated temporary "
    "mail failures."
)
NO_LONGER_FLAGGED_MESSAGE = (
    "Not sent: this recipient had no flagged facilities when the email was retried."
)
ALERT_DISABLED_MESSAGE = (
    "Not sent: the alert was disabled before the email was retried."
)

# Recipient-level rejections. 5.7.x is excluded because it reports a policy
# decision about the sender, which says nothing about the address itself.
_INVALID_ADDRESS_CODES = {550, 551, 553}
_POLICY_STATUS = "5.7."
# Providers append a per-message reference that makes messages impossible to group
_TRAILING_REFERENCE = re.compile(r"\s*\([0-9a-fA-F-]{16,}\)\s*$")


class FailureKind(Enum):
    """How a failed send is handled."""

    INVALID_ADDRESS = "invalid_address"  # pause the address
    TEMPORARY = "temporary"  # retry later
    OTHER = "other"  # record only


class EmailFailure(NamedTuple):
    kind: FailureKind
    message: str


def paused_address_message(days: int) -> str:
    """Why an email was not attempted because its address was recently rejected."""
    return (
        f"Not sent: this address was rejected as invalid within the last {days} "
        "days. Correct the user's email address to resume sending."
    )


def _server_text(response: bytes | str) -> str:
    text = (
        response.decode("utf-8", "replace") if isinstance(response, bytes) else response
    )
    return _TRAILING_REFERENCE.sub("", text).strip()


def _describe_response(code: int, response: bytes | str, refused: bool) -> EmailFailure:
    text = _server_text(response)
    detail = f"{code} {text}".strip()
    if (
        refused
        and code in _INVALID_ADDRESS_CODES
        and not text.startswith(_POLICY_STATUS)
    ):
        return EmailFailure(
            FailureKind.INVALID_ADDRESS,
            f"{INVALID_ADDRESS_PREFIX}the mail provider rejected it ({detail}).",
        )
    if 400 <= code < 500:
        return EmailFailure(
            FailureKind.TEMPORARY,
            f"{RETRY_PREFIX}the mail provider temporarily refused the email "
            f"({detail}).",
        )
    return EmailFailure(
        FailureKind.OTHER, f"The mail provider rejected the email ({detail})."
    )


def classify_email_error(ex: Exception) -> EmailFailure:
    """Describe a failed send for the audit table and say how to handle it."""
    if isinstance(ex, smtplib.SMTPRecipientsRefused) and ex.recipients:
        code, response = next(iter(ex.recipients.values()))
        return _describe_response(code, response, refused=True)
    if isinstance(ex, smtplib.SMTPAuthenticationError):
        return EmailFailure(
            FailureKind.OTHER,
            "The mail server rejected the login. Check the SMTP username and password.",
        )
    if isinstance(ex, smtplib.SMTPResponseException):
        return _describe_response(ex.smtp_code, ex.smtp_error, refused=False)
    # Refused connections, timeouts and DNS failures. SMTPException also derives
    # from OSError, so its remaining subclasses are handled separately.
    if isinstance(ex, OSError) and not isinstance(ex, smtplib.SMTPException):
        return EmailFailure(
            FailureKind.TEMPORARY,
            f"{RETRY_PREFIX}could not reach the mail server ({type(ex).__name__}).",
        )
    if isinstance(ex, smtplib.SMTPServerDisconnected):
        return EmailFailure(
            FailureKind.TEMPORARY,
            f"{RETRY_PREFIX}the mail server closed the connection.",
        )
    return EmailFailure(FailureKind.OTHER, f"{type(ex).__name__}: {ex}"[:1000])
