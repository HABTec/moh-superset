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
"""Queue and send the emails of the feedback loop.

Emails are saved with the change that causes them, so a mail outage loses
nothing. They hold a link rather than the conversation, so feedback stays on the
portal. Nothing is queued or sent unless ``MOH_FEEDBACK_EMAILS_ENABLED`` is set.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from flask import current_app
from markupsafe import escape

from superset.moh_alerts.email_errors import (
    classify_email_error,
    EmailFailure,
    FailureKind,
)
from superset.moh_feedback.org_units import OrgUnitLookupError
from superset.utils import json

logger = logging.getLogger(__name__)

PENDING = "pending"
SENT = "sent"
FAILED = "failed"
SKIPPED = "skipped"
EXPANDED = "expanded"

RECEIVED = "received"
ASSIGNED = "assigned"
ADDED = "added"
ASKED = "asked"
ANSWERED = "answered"
DECLINED = "declined"
MOVED_SENDER = "moved_sender"
MOVED_UNIT = "moved_unit"
MOVED_ASSIGNEE = "moved_assignee"
REPLIED = "replied"
HANDLER_REPLY = "handler_reply"
SENDER_MESSAGE = "sender_message"
REOPENED = "reopened"
NOT_SOLVED = "not_solved"
AUTO_CLOSED = "auto_closed"
DIGEST = "digest"

DEFAULT_BATCH_SIZE = 50
DEFAULT_AUTO_CLOSE_DAYS = 14
_RETRY_DELAYS = (
    timedelta(minutes=5),
    timedelta(minutes=30),
    timedelta(hours=2),
    timedelta(hours=6),
)
# A provider refusing several in a row is overloaded, so the rest can wait
_MAX_TEMPORARY_FAILURES_PER_RUN = 3
_ERROR_MAX_LENGTH = 1000

# Subject text and message for each email. Subjects hold only fixed text and the
# reference, as names come from user accounts and do not belong in mail headers.
_TEMPLATES = {
    RECEIVED: ("We received your feedback", "Your feedback was received."),
    ASSIGNED: (
        "Feedback assigned to you",
        "{actor} assigned this feedback to you.",
    ),
    ADDED: (
        "You were added to feedback",
        "{actor} added you to this feedback. You can read it and reply. "
        "You are not responsible for handling it.",
    ),
    ASKED: (
        "A question about your feedback",
        "{actor} needs more information. Please open your feedback and reply.",
    ),
    ANSWERED: (
        "Your feedback has an answer",
        "{actor} answered your feedback. Please open it and say whether this "
        "solved your problem. It closes automatically in {auto_close_days} days "
        "if you do not respond.",
    ),
    DECLINED: (
        "Your feedback was declined",
        "{actor} declined your feedback. Please open it to read the reason.",
    ),
    MOVED_SENDER: (
        "Your feedback was passed on",
        "Your feedback was passed to {unit}. Please open it to see why.",
    ),
    MOVED_UNIT: (
        "Feedback was passed to your unit",
        "This feedback was passed to {unit}, and your unit is now responsible.",
    ),
    MOVED_ASSIGNEE: (
        "Feedback assigned to you was passed on",
        "This feedback was passed to {unit}. You are no longer responsible for "
        "it, and you can still read it.",
    ),
    HANDLER_REPLY: (
        "New message about your feedback",
        "{actor} wrote a message about your feedback. Please open it to read it.",
    ),
    SENDER_MESSAGE: (
        "The sender added information",
        "The sender added more information. Please open the feedback.",
    ),
    REOPENED: (
        "The sender reopened this feedback",
        "The sender reopened this feedback. Please open it to see why.",
    ),
    REPLIED: (
        "The sender replied to your question",
        "The sender replied. Please open the feedback.",
    ),
    NOT_SOLVED: (
        "The sender says this is not solved",
        "The sender says the answer did not solve the problem. "
        "Please open the feedback.",
    ),
    AUTO_CLOSED: (
        "Your feedback was closed",
        "Your feedback was closed because there was no response for "
        "{auto_close_days} days.",
    ),
}


def emails_enabled() -> bool:
    return bool(current_app.config.get("MOH_FEEDBACK_EMAILS_ENABLED", False))


def auto_close_days() -> int:
    return current_app.config.get(
        "MOH_FEEDBACK_AUTO_CLOSE_DAYS", DEFAULT_AUTO_CLOSE_DAYS
    )


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


def _notification_model() -> Any:
    from superset.models.moh_feedback import (  # pylint: disable=import-outside-toplevel
        MohFeedbackNotification,
    )

    return MohFeedbackNotification


def queue(  # pylint: disable=too-many-arguments
    item: Any,
    kind: str,
    user_id: int | None = None,
    unit_id: str | None = None,
    actor_id: int | None = None,
    actor_name: str | None = None,
) -> None:
    """Save an email for one person, or for the handlers of one unit.

    People are not told about what they did themselves.
    """
    if not emails_enabled() or (user_id is None and unit_id is None):
        return
    if user_id is not None and user_id == actor_id:
        return
    item.notifications.append(
        _notification_model()(
            user_id=user_id,
            unit_id=unit_id,
            exclude_user_id=actor_id,
            kind=kind,
            actor_name=actor_name[:255] if actor_name else None,
            status=PENDING,
            next_attempt_on=_utc_now(),
        )
    )


def notify_handlers(
    item: Any, kind: str, actor_id: int | None, unit_id: str | None
) -> None:
    """Tell the assignee, or the responsible unit if nobody is assigned."""
    if item.assigned_to_fk is not None:
        queue(item, kind, user_id=item.assigned_to_fk, actor_id=actor_id)
    else:
        queue(item, kind, unit_id=unit_id, actor_id=actor_id)


def notify_moved(
    item: Any, previous_assignee: int | None, unit_id: str, actor: Any
) -> None:
    """Tell the sender, the earlier assignee and the unit now responsible."""
    queue(item, MOVED_SENDER, user_id=item.created_by_fk, actor_id=actor.id)
    queue(item, MOVED_ASSIGNEE, user_id=previous_assignee, actor_id=actor.id)
    queue(item, MOVED_UNIT, unit_id=unit_id, actor_id=actor.id)


def _web_base() -> str:
    config = current_app.config
    return str(
        config.get("MOH_FEEDBACK_WEB_HOST") or config.get("MOH_ALERTS_WEB_HOST", "")
    ).rstrip("/")


def _email_html(heading: str, text: str, link: str, link_text: str) -> str:
    return (
        '<div style="font-family:Arial,sans-serif;font-size:15px;color:#10243e">'
        f'<h2 style="font-size:18px">{escape(heading)}</h2>'
        f"<p>{escape(text)}</p>"
        f'<p><a href="{escape(link)}" style="background:#1a5cff;color:#fff;'
        "padding:9px 16px;border-radius:6px;text-decoration:none;"
        f'display:inline-block">{escape(link_text)}</a></p>'
        '<p style="color:#5b6b7f;font-size:13px">Please sign in to reply. '
        "Replies sent to this email are not read.</p></div>"
    )


def _render_digest(row: Any) -> tuple[str, str]:
    counts = json.loads(row.detail)
    text = (
        f"Waiting for your unit: {counts['new']} new and {counts['overdue']} overdue."
    )
    html = _email_html(
        "Your feedback summary",
        text,
        f"{_web_base()}/moh/feedback/waiting",
        "Open Waiting on me",
    )
    return "Your feedback summary", html


def render(row: Any) -> tuple[str, str]:
    """Return the subject and HTML body of a queued email."""
    if row.kind == DIGEST:
        return _render_digest(row)
    title, template = _TEMPLATES[row.kind]
    item = row.feedback
    text = template.format(
        actor=row.actor_name or "Someone",
        unit=item.target_unit_name or "another unit",
        auto_close_days=auto_close_days(),
    )
    link = f"{_web_base()}/moh/feedback/{item.uuid}"
    return f"[{item.reference}] {title}", _email_html(
        title, text, link, "Open the feedback"
    )


def _recipient_email(user_id: int, db: Any) -> str | None:
    """Return the email of an active account, read when the message is sent."""
    from superset.extensions import (  # pylint: disable=import-outside-toplevel
        security_manager,
    )

    user_model = security_manager.user_model
    row = (
        db.session.query(user_model.email)
        .filter(user_model.id == user_id, user_model.active)
        .one_or_none()
    )
    return str(row[0]).strip() if row and row[0] else None


def _send_email(address: str, subject: str, body: str) -> None:
    from superset.utils.core import (  # pylint: disable=import-outside-toplevel
        send_email_smtp,
    )

    send_email_smtp(
        to=address,
        subject=subject,
        html_content=body,
        config=current_app.config,
        data={},
        images={},
    )


def _skip_reason(address: str | None) -> str | None:
    """Return why an email must not be sent to this address, or None if it can."""
    # pylint: disable=import-outside-toplevel
    from superset.moh_alerts.tasks import _is_reserved_test_email, _paused_addresses

    if not address:
        return "No active account with an email address."
    allowed = current_app.config.get("MOH_FEEDBACK_EMAIL_ONLY_TO")
    if allowed is not None and address.lower() not in {a.lower() for a in allowed}:
        return "Not on the pilot list."
    if _is_reserved_test_email(address):
        return "Reserved test address."
    if _paused_addresses([address]):
        return "This address was recently rejected as invalid."
    return None


def _retry_or_give_up(row: Any, failure: EmailFailure, now: datetime) -> None:
    row.attempts = (row.attempts or 0) + 1
    row.error_message = failure.message[:_ERROR_MAX_LENGTH]
    if failure.kind == FailureKind.INVALID_ADDRESS or row.attempts > len(_RETRY_DELAYS):
        row.status = FAILED
    else:
        row.next_attempt_on = now + _RETRY_DELAYS[row.attempts - 1]


def _deliver(row: Any, db: Any, now: datetime) -> EmailFailure | None:
    """Send one queued email and record what happened."""
    address = _recipient_email(row.user_id, db)
    if reason := _skip_reason(address):
        row.status = SKIPPED
        row.error_message = reason
        return None
    try:
        subject, body = render(row)
        _send_email(str(address), subject, body)
    except Exception as ex:  # pylint: disable=broad-except
        logger.warning("Feedback email %s failed: %s", row.id, type(ex).__name__)
        failure = classify_email_error(ex)
        _retry_or_give_up(row, failure, now)
        return failure
    row.status = SENT
    row.sent_on = now
    row.error_message = None
    return None


def _expand_unit_rows(db: Any, model: Any, now: datetime, limit: int) -> None:
    """Replace each queued email for a unit with one for each of its handlers."""
    # pylint: disable=import-outside-toplevel
    from superset.moh_feedback.routing import unit_handlers

    rows = (
        db.session.query(model)
        .filter(model.status == PENDING, model.unit_id.isnot(None))
        .filter(model.next_attempt_on <= now)
        .order_by(model.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
        .all()
    )
    for row in rows:
        try:
            people = unit_handlers(row.unit_id, row.feedback.created_by_fk)
        except OrgUnitLookupError:
            row.next_attempt_on = now + _RETRY_DELAYS[0]
            continue
        for person in _others(people, row.exclude_user_id):
            db.session.add(
                model(
                    feedback_id=row.feedback_id,
                    user_id=person.id,
                    kind=row.kind,
                    actor_name=row.actor_name,
                    status=PENDING,
                    next_attempt_on=now,
                )
            )
        row.status = EXPANDED
    db.session.commit()


def _others(people: Iterable[Any], excluded_user_id: int | None) -> list[Any]:
    return [person for person in people if person.id != excluded_user_id]


def deliver_due(db: Any, now: datetime | None = None) -> None:
    """Send the emails that are due, up to the batch size."""
    moment = now or _utc_now()
    model = _notification_model()
    limit = current_app.config.get(
        "MOH_FEEDBACK_NOTIFICATION_BATCH", DEFAULT_BATCH_SIZE
    )
    _expand_unit_rows(db, model, moment, limit)
    due_ids = [
        row[0]
        for row in db.session.query(model.id)
        .filter(
            model.status == PENDING,
            model.user_id.isnot(None),
            model.next_attempt_on <= moment,
        )
        .order_by(model.next_attempt_on, model.id)
        .limit(limit)
        .all()
    ]
    db.session.rollback()
    temporary_failures = 0
    for row_id in due_ids:
        row = (
            db.session.query(model)
            .filter_by(id=row_id, status=PENDING)
            .with_for_update(skip_locked=True)
            .one_or_none()
        )
        if row is None:
            db.session.rollback()
            continue
        failure = _deliver(row, db, moment)
        db.session.commit()
        if failure is not None and failure.kind == FailureKind.TEMPORARY:
            temporary_failures += 1
            if temporary_failures >= _MAX_TEMPORARY_FAILURES_PER_RUN:
                logger.warning("Feedback emails paused for this run")
                return
