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

import smtplib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from superset.moh_alerts import tasks
from superset.moh_alerts.email_errors import (
    classify_email_error,
    FailureKind,
    GAVE_UP_PREFIX,
    INVALID_ADDRESS_PREFIX,
    NO_LONGER_FLAGGED_MESSAGE,
    RETRY_PREFIX,
    SENDING_DEFERRED_MESSAGE,
)
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
    state: dict[str, Any] = {
        "session": session,
        "fail": set(),
        "sent": {},
        "paused": set(),
        "errors": {},
        "attempted": [],
        "scheduled": [],
    }

    class Recipient(_Record):
        pass

    class Facility(_Record):
        pass

    def send(to: str, **kwargs: Any) -> None:
        state["attempted"].append(to)
        if to in state["errors"]:
            raise state["errors"][to]
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
        "_paused_addresses": lambda emails: state["paused"],
    }
    for name, stub in stubs.items():
        monkeypatch.setattr(tasks, name, stub)
    monkeypatch.setattr(
        tasks.retry_emails,
        "apply_async",
        lambda args, countdown: state["scheduled"].append((args, countdown)),
    )
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


REFUSED_INVALID = smtplib.SMTPRecipientsRefused(
    {
        "a@moh.test": (
            550,
            b"5.1.1 [R1] Invalid recipient (5e82a80c-d700-11f1-844b-df8125a0c701)",
        )
    }
)
REFUSED_RATE_LIMIT = smtplib.SMTPRecipientsRefused(
    {"a@moh.test": (451, b"4.7.1 [R6] You have more than 50 failed deliveries")}
)


def test_classifies_rejected_address_without_address_or_reference() -> None:
    failure = classify_email_error(REFUSED_INVALID)

    assert failure.kind is FailureKind.INVALID_ADDRESS
    assert failure.message == (
        f"{INVALID_ADDRESS_PREFIX}the mail provider rejected it "
        "(550 5.1.1 [R1] Invalid recipient)."
    )


def test_classifies_provider_limit_as_temporary() -> None:
    failure = classify_email_error(REFUSED_RATE_LIMIT)

    assert failure.kind is FailureKind.TEMPORARY
    assert failure.message.startswith(RETRY_PREFIX)
    assert "more than 50 failed deliveries" in failure.message


def test_policy_rejection_does_not_blame_the_address() -> None:
    failure = classify_email_error(
        smtplib.SMTPRecipientsRefused({"a@moh.test": (550, b"5.7.1 Relaying denied")})
    )

    assert failure.kind is FailureKind.OTHER


@pytest.mark.parametrize(
    "error",
    [
        smtplib.SMTPServerDisconnected("closed"),
        ConnectionRefusedError(111, "refused"),
        TimeoutError(),
        smtplib.SMTPDataError(421, b"try again"),
    ],
)
def test_connection_problems_and_4xx_are_temporary(error: Exception) -> None:
    assert classify_email_error(error).kind is FailureKind.TEMPORARY


def test_login_failure_is_readable_and_not_retried() -> None:
    failure = classify_email_error(smtplib.SMTPAuthenticationError(535, b"bad creds"))

    assert failure.kind is FailureKind.OTHER
    assert "SMTP username and password" in failure.message
    assert "bad creds" not in failure.message


def test_paused_address_is_recorded_but_not_attempted(run: dict[str, Any]) -> None:
    run["paused"] = {"hp_user@moh.test"}
    delivery = _delivery()

    tasks._run_delivery(_alert(), delivery)

    assert run["attempted"] == ["region_user@moh.test"]
    paused = next(r for r in _added(run, run["Recipient"]) if r.username == "hp_user")
    assert paused.sent is False
    assert paused.error_message.startswith("Not sent: this address was rejected")
    # Recording a pause must not look like a fresh rejection or a pending retry
    assert not paused.error_message.startswith(INVALID_ADDRESS_PREFIX)
    assert not paused.error_message.startswith(RETRY_PREFIX)
    assert run["scheduled"] == []


def test_invalid_address_is_not_retried(run: dict[str, Any]) -> None:
    run["errors"]["hp_user@moh.test"] = REFUSED_INVALID

    tasks._run_delivery(_alert(), _delivery())

    failed = next(r for r in _added(run, run["Recipient"]) if r.username == "hp_user")
    assert failed.error_message.startswith(INVALID_ADDRESS_PREFIX)
    assert run["scheduled"] == []


def test_temporary_failure_schedules_retry_after_commit(run: dict[str, Any]) -> None:
    run["errors"]["hp_user@moh.test"] = REFUSED_RATE_LIMIT
    delivery = _delivery()

    tasks._run_delivery(_alert(), delivery)

    assert run["scheduled"] == [((7, 1), 3900)]
    assert delivery.recipients == 1


def test_repeated_temporary_failures_stop_further_attempts(
    run: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    users = {f"u{i}": ["F1"] for i in range(5)}
    monkeypatch.setattr(tasks, "resolve", lambda *a, **k: (users, 0))
    run["errors"].update({f"u{i}@moh.test": REFUSED_RATE_LIMIT for i in range(5)})

    tasks._run_delivery(_alert(), _delivery())

    assert len(run["attempted"]) == tasks.MAX_CONSECUTIVE_TEMPORARY_FAILURES
    recipients = _added(run, run["Recipient"])
    assert len(recipients) == 5
    assert recipients[-1].error_message == SENDING_DEFERRED_MESSAGE
    assert len(run["scheduled"]) == 1


def _pending_row(username: str) -> Any:
    return SimpleNamespace(
        username=username,
        email=f"{username}@moh.test",
        org_unit_id="OU1",
        sent=False,
        sent_at=None,
        subject="old",
        facilities=9,
        facilities_shown=9,
        error_message=f"{RETRY_PREFIX}the mail provider temporarily refused.",
    )


def test_retry_marks_row_sent_and_counts_recipient(run: dict[str, Any]) -> None:
    row = _pending_row("hp_user")
    delivery = SimpleNamespace(id=7, period="201901", recipients=1)

    tasks._retry_pending(_alert(), delivery, [row])

    assert run["attempted"] == ["hp_user@moh.test"]
    assert row.sent is True
    assert row.sent_at is not None
    assert row.error_message is None
    assert row.facilities == 1
    assert delivery.recipients == 2


def test_retry_skips_recipient_with_nothing_flagged(run: dict[str, Any]) -> None:
    row = _pending_row("someone_else")

    tasks._retry_pending(
        _alert(), SimpleNamespace(id=7, period="201901", recipients=0), [row]
    )

    assert run["attempted"] == []
    assert row.error_message == NO_LONGER_FLAGGED_MESSAGE


def test_retry_records_new_failure_and_stays_pending(run: dict[str, Any]) -> None:
    run["errors"]["hp_user@moh.test"] = REFUSED_RATE_LIMIT
    row = _pending_row("hp_user")

    tasks._retry_pending(
        _alert(), SimpleNamespace(id=7, period="201901", recipients=0), [row]
    )

    assert row.sent is False
    assert "more than 50 failed deliveries" in row.error_message
    assert row.error_message.startswith(RETRY_PREFIX)


def test_schedules_second_retry_then_gives_up(run: dict[str, Any]) -> None:
    row = _pending_row("hp_user")
    delivery = _delivery()

    tasks._schedule_retry_or_give_up(delivery, [row], attempt=2)
    assert run["scheduled"] == [((7, 2), 7200)]
    assert row.error_message.startswith(RETRY_PREFIX)

    tasks._schedule_retry_or_give_up(delivery, [row], attempt=3)
    assert len(run["scheduled"]) == 1
    assert row.error_message == (
        f"{GAVE_UP_PREFIX}the mail provider temporarily refused."
    )


def test_broker_outage_does_not_fail_the_run(
    run: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(args: Any, countdown: int) -> None:
        raise ConnectionError("broker down")

    monkeypatch.setattr(tasks.retry_emails, "apply_async", unavailable)
    run["errors"]["hp_user@moh.test"] = REFUSED_RATE_LIMIT
    delivery = _delivery()

    tasks._run_delivery(_alert(), delivery)

    assert delivery.status == "success"


def test_paused_addresses_uses_only_recent_rejections(
    session: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from superset.models.moh_alert import (
        MohAlertDelivery,
        MohAlertDeliveryRecipient,
    )

    bind = session.get_bind()
    MohAlertDelivery.__table__.create(bind)
    MohAlertDeliveryRecipient.__table__.create(bind)
    monkeypatch.setattr(tasks, "_load_db", lambda: SimpleNamespace(session=session))
    now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    recent = MohAlertDelivery(id=1, alert_id=1, started_at=now - timedelta(days=2))
    old = MohAlertDelivery(id=2, alert_id=1, started_at=now - timedelta(days=30))
    rejected = f"{INVALID_ADDRESS_PREFIX}the mail provider rejected it."
    session.add_all(
        [
            recent,
            old,
            MohAlertDeliveryRecipient(
                delivery_id=1, email="Bad@moh.test", sent=False, error_message=rejected
            ),
            MohAlertDeliveryRecipient(
                delivery_id=2, email="old@moh.test", sent=False, error_message=rejected
            ),
            MohAlertDeliveryRecipient(
                delivery_id=1,
                email="busy@moh.test",
                sent=False,
                error_message=f"{RETRY_PREFIX}limit",
            ),
            MohAlertDeliveryRecipient(
                delivery_id=1,
                email="still@moh.test",
                sent=False,
                error_message="Not sent: this address was rejected as invalid",
            ),
        ]
    )
    session.flush()

    paused = tasks._paused_addresses(
        ["bad@moh.test", "old@moh.test", "busy@moh.test", "still@moh.test"]
    )

    assert paused == {"bad@moh.test"}


def test_email_describes_the_data_escaped_and_in_order() -> None:
    extra = {
        **EXTRA,
        "threshold": "Flagged when value < 85",
        "data_source": "DHIS2 monthly reports",
        "time_range": "Latest reported month",
        "formula": "Acceptors / women of reproductive age x 100",
    }

    html = render_alert_email(_alert(), extra, ROWS[:1], None)

    assert "About this data" in html
    assert "Flagged when value &lt; 85" in html
    positions = [
        html.index(text)
        for text in ("Data source", "Time range", "Formula", "Threshold")
    ]
    assert positions == sorted(positions)


def test_email_shows_only_the_descriptions_provided() -> None:
    html = render_alert_email(
        _alert(), {**EXTRA, "data_source": "DHIS2"}, ROWS[:1], None
    )

    assert "Data source" in html
    assert "Threshold" not in html


def test_email_omits_data_section_when_nothing_is_configured() -> None:
    assert "About this data" not in render_alert_email(_alert(), EXTRA, ROWS[:1], None)
