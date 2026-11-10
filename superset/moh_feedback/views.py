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
"""Feedback pages, under /moh/feedback, for every signed-in user.

Imported by ``superset_config.py`` while the configuration loads, before the
SQLAlchemy models can be imported, so models are loaded inside functions.
"""

from __future__ import annotations

import logging
import math
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit

from flask import (
    abort,
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_login import current_user
from flask_wtf.csrf import generate_csrf, validate_csrf
from sqlalchemy import and_, case, exists, or_
from sqlalchemy.exc import IntegrityError
from wtforms import ValidationError

from superset.moh_feedback import attachments, notifications
from superset.moh_feedback.attachments import StoredScreenshot
from superset.moh_feedback.deadlines import (
    HIGH,
    local_date,
    LOCAL_TIMEZONE,
    LOW,
    NORMAL,
    PRIORITIES,
    refresh_deadlines,
)
from superset.moh_feedback.handover import (
    hand_over,
    responsible_unit_id,
    sender_username,
)
from superset.moh_feedback.notifications import notify_handlers, queue
from superset.moh_feedback.org_units import (
    get_units,
    get_user_units,
    OrgUnit,
    OrgUnitLookupError,
    selectable_units,
)
from superset.moh_feedback.people import (
    active_user_ids,
    find_people,
    FoundPerson,
    is_searchable,
    person_token,
    read_person_token,
)
from superset.moh_feedback.routing import (
    DEFAULT_HANDLER_ROLES,
    describe_units_below,
    find_destination_down,
    find_destination_up,
    is_below,
    unit_handlers,
)
from superset.moh_feedback.stats import in_area, summarise
from superset.moh_feedback.workflow import (
    ACTIONS,
    allowed_actions,
    ANSWER,
    ANSWERED,
    apply_action,
    apply_participant_comment,
    apply_reopen,
    apply_sender_decision,
    apply_sender_message,
    apply_sender_reply,
    ASK,
    ASSIGN,
    ASSIGNED,
    CLOSED,
    CONFIRMED,
    DECLINE,
    DECLINED,
    IN_REVIEW,
    is_overdue,
    MOVE_ACTION,
    NEEDS_INFO,
    NEW,
    NO_RESPONSE,
    overdue_condition,
    Person,
    REOPEN_ACTION,
    REPLY,
    SET_PRIORITY,
)

logger = logging.getLogger(__name__)

moh_feedback_bp = Blueprint(
    "moh_feedback",
    __name__,
    url_prefix="/moh/feedback",
    template_folder="templates",
)

FEEDBACK_TYPES = (
    ("problem", "Problem"),
    ("wrong_data", "Wrong data"),
    ("question", "Question"),
    ("suggestion", "Suggestion"),
)
STATUS_LABELS = {
    NEW: "New",
    IN_REVIEW: "In review",
    ASSIGNED: "Assigned",
    NEEDS_INFO: "Needs info",
    ANSWERED: "Answered",
    CLOSED: "Closed",
    DECLINED: "Declined",
    CONFIRMED: "Closed",
    NO_RESPONSE: "Closed (no response)",
}
EVENT_LABELS = {
    "created": "Feedback sent",
    "routed": "Sent to",
    "routing_pending": "Waiting for routing",
    "review_started": "Review started",
    "assigned": "Assigned to",
    "asked": "Question for the sender",
    "answered": "Answer",
    "declined": "Declined",
    "internal_note": "Internal note",
    "sender_reply": "Reply from the sender",
    "sender_solved": "Sender confirmed this is solved",
    "sender_not_solved": "Sender said this is not solved",
    "participant_comment": "Comment",
    "person_added": "Added to this feedback:",
    "person_removed": "Removed from this feedback:",
    "priority_changed": "Priority set to",
    "moved": "Passed on",
    "replied": "Message",
    "sender_message": "More information from the sender",
    "reopened": "Reopened by the sender",
    "content_hidden": "Hidden by a handler:",
    "auto_closed": "Closed because there was no response",
}
DIRECTIONS = ("up", "down")
STATS_DAY_OPTIONS = (30, 90, 365)
DEFAULT_STATS_DAYS = 90
SOLVED = "solved"
NOT_SOLVED = "not_solved"
UNIT_SEARCH_MIN_LENGTH = 2
UNIT_SEARCH_LIMIT = 20
ITEMS_PER_PAGE = 25
DISPLAY_TIMEZONE = LOCAL_TIMEZONE
PRIORITY_LABELS = {HIGH: "High", NORMAL: "Normal", LOW: "Low"}
MESSAGE_MIN_LENGTH = 10
MESSAGE_MAX_LENGTH = 2000
PAGE_URL_MAX_LENGTH = 2048
DEFAULT_MAX_PER_HOUR = 10
DEFAULT_MAX_PEOPLE_PER_ITEM = 5
DEFAULT_MAX_PEOPLE_ADDED_PER_DAY = 20
DEFAULT_MAX_PERSON_SEARCHES = 30
PERSON_SEARCH_WINDOW = timedelta(minutes=10)
PERSON_SEARCH_LIMIT = 10
# Enough to report going over the limit, without reading an unbounded list
_PERSON_TOKENS_READ = 50
_SENDER_EMAILS = {
    ASK: notifications.ASKED,
    ANSWER: notifications.ANSWERED,
    DECLINE: notifications.DECLINED,
    REPLY: notifications.HANDLER_REPLY,
}
_SENT_REFERENCE_KEY = "moh_feedback_sent_reference"
_SENT_DUE_KEY = "moh_feedback_sent_due"
_UNIT_IDS_KEY = "moh_feedback.unit_ids"
_COUNT_UNITS_KEY = "moh_feedback_count_units"
_COUNT_UNITS_SECONDS = 300
_DASHBOARD_PATH = re.compile(r"^/superset/dashboard/([^/?#]+)")
_SEARCH_MAX_LENGTH = 100
_REFERENCE_SEARCH = re.compile(r"^(?:fb-?)?(\d{1,9})$", re.IGNORECASE)
_FILTER_STATUSES = (NEW, IN_REVIEW, ASSIGNED, NEEDS_INFO, ANSWERED, CLOSED)
_OVERDUE_FILTER = "overdue"
_NEEDS_SENDER = (NEEDS_INFO, ANSWERED)
_SENDER_CAN_ADD = (NEW, IN_REVIEW, ASSIGNED)
DEFAULT_REOPEN_DAYS = 30
_PAGES_NOT_RECORDED = ("/moh/feedback", "/feedback", "/login")
_HIDDEN_LABELS = {"message": "The original message", "event": "A history entry"}
_SUBMISSION_ID = re.compile(r"^[0-9a-f]{32}$")


def _load_db() -> Any:
    from superset.extensions import db  # pylint: disable=import-outside-toplevel

    return db


def _load_models() -> tuple[Any, Any]:
    # pylint: disable=import-outside-toplevel
    from superset.models.moh_feedback import MohFeedback, MohFeedbackEvent

    return MohFeedback, MohFeedbackEvent


@moh_feedback_bp.app_template_filter("moh_feedback_time")
def format_time(value: datetime) -> str:
    """Show a stored UTC time in Addis Ababa time, such as ``9 Nov 2026, 10:21``."""
    local = value.replace(tzinfo=timezone.utc).astimezone(DISPLAY_TIMEZONE)
    return f"{local.day} {local:%b %Y, %H:%M}"


def _load_participant_model() -> Any:
    from superset.models.moh_feedback import (  # pylint: disable=import-outside-toplevel
        MohFeedbackParticipant,
    )

    return MohFeedbackParticipant


def _load_search_model() -> Any:
    from superset.models.moh_feedback import (  # pylint: disable=import-outside-toplevel
        MohFeedbackPersonSearch,
    )

    return MohFeedbackPersonSearch


def _load_attachment_model() -> Any:
    from superset.models.moh_feedback import (  # pylint: disable=import-outside-toplevel
        MohFeedbackAttachment,
    )

    return MohFeedbackAttachment


def _load_user_model() -> Any:
    from flask_appbuilder.security.sqla.models import (  # pylint: disable=import-outside-toplevel
        User,
    )

    return User


def _page_title(page_url: str) -> str | None:
    """Return the name of the dashboard at a portal address, if it is one."""
    from superset.models.dashboard import (  # pylint: disable=import-outside-toplevel
        Dashboard,
    )

    match = _DASHBOARD_PATH.match(page_url)
    if match is None:
        return None
    key = match.group(1)
    condition = Dashboard.id == int(key) if key.isdigit() else Dashboard.slug == key
    row = _load_db().session.query(Dashboard.dashboard_title).filter(condition).first()
    return row[0] if row else None


def _referrer_page() -> str | None:
    """Return the portal page the user came from, if there is a useful one."""
    parts = urlsplit(request.referrer or "")
    if parts.netloc != request.host or parts.path.startswith(_PAGES_NOT_RECORDED):
        return None
    query = f"?{parts.query}" if parts.query else ""
    return safe_page_url(f"{parts.path}{query}")


def _load_access_model() -> Any:
    # pylint: disable=import-outside-toplevel
    from superset.models.moh_feedback import MohFeedbackUnitAccess

    return MohFeedbackUnitAccess


def _is_signed_in() -> bool:
    return bool(getattr(current_user, "is_authenticated", False))


def _can_handle() -> bool:
    """Return whether the signed-in user has a role that handles feedback."""
    if not _is_signed_in():
        return False
    roles = current_app.config.get("MOH_FEEDBACK_HANDLER_ROLES", DEFAULT_HANDLER_ROLES)
    return any(role.name in roles for role in current_user.roles)


@moh_feedback_bp.context_processor
def _layout_context() -> dict[str, Any]:
    return {"show_waiting_tab": _can_handle(), **_tab_counts()}


def _needs_action_filter(feedback_model: Any) -> Any:
    """Match what a handler should deal with, including work nobody can do."""
    user_model = _load_user_model()
    assignee_left = exists().where(
        user_model.id == feedback_model.assigned_to_fk, ~user_model.active
    )
    return or_(
        feedback_model.status.in_((NEW, IN_REVIEW)),
        and_(
            feedback_model.status == ASSIGNED,
            or_(feedback_model.assigned_to_fk == current_user.id, assignee_left),
        ),
    )


def _items_at_units(db: Any, unit_ids: set[str]) -> Any:
    """Query the items these units are responsible for, except the user's own."""
    feedback_model, _ = _load_models()
    access_model = _load_access_model()
    return (
        db.session.query(feedback_model)
        .join(access_model, access_model.feedback_id == feedback_model.id)
        .filter(
            access_model.is_current,
            access_model.unit_id.in_(unit_ids),
            or_(
                feedback_model.created_by_fk.is_(None),
                feedback_model.created_by_fk != current_user.id,
            ),
        )
    )


def _unit_ids_for_count() -> set[str]:
    """Return the user's units for a tab count, remembered for a few minutes.

    Every page shows the count, so a look-up per page would keep database
    connections busy under load. Access is never decided from this copy.
    """
    remembered = session.get(_COUNT_UNITS_KEY)
    if remembered and time.time() - remembered[0] < _COUNT_UNITS_SECONDS:
        return set(remembered[1])
    unit_ids = _users_unit_ids()
    session[_COUNT_UNITS_KEY] = [time.time(), sorted(unit_ids)]
    return unit_ids


def _tab_counts() -> dict[str, int]:
    """Count what is waiting for the signed-in user, for the tabs."""
    if not _is_signed_in():
        return {}
    db = _load_db()
    feedback_model, _ = _load_models()
    counts = {
        "mine_count": db.session.query(feedback_model)
        .filter(
            feedback_model.created_by_fk == current_user.id,
            feedback_model.status.in_(_NEEDS_SENDER),
        )
        .count()
    }
    if _can_handle():
        try:
            unit_ids = _unit_ids_for_count()
        except OrgUnitLookupError:
            return counts
        counts["waiting_count"] = (
            _items_at_units(db, unit_ids)
            .filter(_needs_action_filter(feedback_model))
            .count()
        )
    return counts


@moh_feedback_bp.context_processor
def _deadline_helpers() -> dict[str, Any]:
    return {
        "deadline_text": _deadline_text,
        "item_overdue": lambda item: is_overdue(item, _utc_now()),
        "priority_labels": PRIORITY_LABELS,
        "show_stats_tab": _can_handle(),
        "item_needs_sender": lambda item: item.status in _NEEDS_SENDER,
    }


def _deadline_text(value: datetime) -> str:
    """Show a deadline as its Addis Ababa date, such as ``9 Nov 2026``."""
    day = local_date(value)
    return f"{day.day} {day:%b %Y}"


def _paged(query: Any, *order: Any) -> tuple[list[Any], int, int]:
    """Return one page of ``query``, the page number and the page count."""
    pages = max(math.ceil(query.count() / ITEMS_PER_PAGE), 1)
    page = min(max(request.args.get("page", 1, type=int), 1), pages)
    items = (
        query.order_by(*order)
        .offset((page - 1) * ITEMS_PER_PAGE)
        .limit(ITEMS_PER_PAGE)
        .all()
    )
    return items, page, pages


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


def safe_page_url(raw: str | None) -> str | None:
    """Return ``raw`` if it is a path on this site, otherwise None."""
    candidate = (raw or "").strip()
    if (
        not candidate.startswith("/")
        or candidate.startswith("//")
        or len(candidate) > PAGE_URL_MAX_LENGTH
        or "\\" in candidate
        or any(ord(character) < 32 for character in candidate)
    ):
        return None
    parts = urlsplit(candidate)
    return None if parts.scheme or parts.netloc else candidate


def clean_message(raw: str) -> str:
    """Normalise text as the browser counted it, without what Postgres rejects.

    Browsers limit a line break to one character but submit two, and Postgres
    cannot store the null character.
    """
    return raw.replace("\r\n", "\n").replace("\x00", "").strip()


def _sender_name() -> str:
    full_name = " ".join(
        part for part in (current_user.first_name, current_user.last_name) if part
    )
    return (full_name or current_user.username)[:255]


def _sender_role() -> str:
    return ", ".join(sorted(role.name for role in current_user.roles))[:255]


def _upper_destination(lookup: list[OrgUnit] | None) -> OrgUnit | None:
    """Return the unit that upward feedback would reach, when that is known."""
    units = selectable_units(lookup or [])
    if lookup is None or len(units) > 1:
        return None
    try:
        return find_destination_up(units[0] if units else None, current_user.username)
    except OrgUnitLookupError:
        return None


def _render_form(
    lookup: list[OrgUnit] | None,
    status: int = 200,
    error: str | None = None,
    values: dict[str, str] | None = None,
    page_url: str | None = None,
) -> tuple[str, int]:
    units = selectable_units(lookup or [])
    upper_destination = _upper_destination(lookup)
    html = render_template(
        "moh_feedback/form.html",
        feedback_types=FEEDBACK_TYPES,
        units=units,
        upper_destination=upper_destination.name if upper_destination else None,
        sends_to_colleagues=bool(
            upper_destination and upper_destination.id in {unit.id for unit in units}
        ),
        can_send_down=any(not unit.leaf for unit in units),
        sender_name=_sender_name(),
        page_url=page_url,
        message_max_length=MESSAGE_MAX_LENGTH,
        error=error,
        values=values or {},
        selected_people=(values or {}).get("people", []),
        screenshot_limit=attachments.max_files(),
        screenshot_megabytes=attachments.max_bytes() // (1024 * 1024),
        max_people=_max_people_per_item(),
        sent_reference=session.pop(_SENT_REFERENCE_KEY, None),
        sent_due=session.pop(_SENT_DUE_KEY, None),
        page_label=_page_title(page_url) if page_url else None,
        submission_id=uuid.uuid4().hex,
        csrf_token=generate_csrf(),
    )
    return html, status


class _RouteRefusedError(Exception):
    """The chosen destination cannot accept this feedback."""

    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def _choose_destination(
    direction: str,
    origin: OrgUnit | None,
    lookup: list[OrgUnit] | None,
    target_unit_id: str,
) -> OrgUnit | None:
    """Return the responsible unit, or None to save the item for routing later."""
    if direction == "up":
        if lookup is None:
            return None
        try:
            return find_destination_up(origin, current_user.username)
        except OrgUnitLookupError:
            return None

    unavailable = (
        "We cannot check the units below you right now. "
        "Please try again, or send this to your upper level."
    )
    if lookup is None:
        raise _RouteRefusedError(unavailable, 503)
    if origin is None:
        raise _RouteRefusedError("You need an org unit to send feedback down.", 400)
    if not target_unit_id:
        raise _RouteRefusedError("Choose the unit to send this to.", 400)
    try:
        target = get_units([target_unit_id]).get(target_unit_id)
        if target is None or target.closed or not is_below(origin, target):
            raise _RouteRefusedError("Choose a unit below yours.", 400)
        destination = find_destination_down(origin, target, current_user.username)
    except OrgUnitLookupError as ex:
        raise _RouteRefusedError(unavailable, 503) from ex
    if destination is None:
        raise _RouteRefusedError(
            "No active user can receive feedback for that unit. Choose another unit.",
            400,
        )
    return destination


def _validation_error(
    feedback_type: str,
    message: str,
    unit_id: str,
    units: list[OrgUnit],
    direction: str,
) -> str | None:
    if direction not in DIRECTIONS:
        return "Choose where to send this feedback."
    if feedback_type not in dict(FEEDBACK_TYPES):
        return "Choose what kind of feedback this is."
    if len(message) < MESSAGE_MIN_LENGTH:
        return f"Please write at least {MESSAGE_MIN_LENGTH} characters."
    if len(message) > MESSAGE_MAX_LENGTH:
        return f"Please keep your message under {MESSAGE_MAX_LENGTH:,} characters."
    if len(units) > 1 and unit_id not in {unit.id for unit in units}:
        return "Choose which of your units this feedback is from."
    return None


def _max_people_per_item() -> int:
    return current_app.config.get(
        "MOH_FEEDBACK_MAX_PEOPLE_PER_ITEM", DEFAULT_MAX_PEOPLE_PER_ITEM
    )


def _chosen_people() -> tuple[list[tuple[str, FoundPerson]], bool]:
    """Read the people selected on the form, one entry per person.

    The flag is False when a selection could not be read, such as an expired one.
    """
    chosen: dict[int, tuple[str, FoundPerson]] = {}
    all_read = True
    for token in request.form.getlist("person_token")[:_PERSON_TOKENS_READ]:
        person = read_person_token(token, current_user.id)
        if person is None:
            all_read = False
        else:
            chosen.setdefault(person.user_id, (token, person))
    return list(chosen.values()), all_read


def _people_added_today(db: Any) -> int:
    participant_model = _load_participant_model()
    return (
        db.session.query(participant_model)
        .filter(
            participant_model.added_by_fk == current_user.id,
            participant_model.added_on > _utc_now() - timedelta(days=1),
        )
        .count()
    )


def _people_problem(
    db: Any, people: list[FoundPerson], already_added: int = 0
) -> str | None:
    """Return why these people cannot be added, or None if they can."""
    if not people:
        return None
    limit = _max_people_per_item()
    if len(people) + already_added > limit:
        return f"You can add up to {limit} people to one item."
    daily_limit = current_app.config.get(
        "MOH_FEEDBACK_MAX_PEOPLE_ADDED_PER_DAY", DEFAULT_MAX_PEOPLE_ADDED_PER_DAY
    )
    if _people_added_today(db) + len(people) > daily_limit:
        return "You have added many people today. Please try again tomorrow."
    wanted = {person.user_id for person in people}
    if active_user_ids(wanted) != wanted:
        return "One of the people you chose can no longer be added."
    return None


def _selection_problem(
    db: Any, people: list[FoundPerson], all_read: bool
) -> str | None:
    if not all_read:
        return "Please search again for the person you want to add."
    return _people_problem(db, people)


def _describe_person(person: FoundPerson) -> str:
    return " · ".join((person.name, *person.paths))


def _attach_person(
    feedback: Any, person: FoundPerson, participant_model: Any, event_model: Any
) -> None:
    """Add a person to an item, recording who added them."""
    feedback.participants.append(
        participant_model(
            user_id=person.user_id,
            added_by_fk=current_user.id,
            display_name=person.name[:255],
            unit_path="\n".join(person.paths) or None,
        )
    )
    feedback.events.append(
        event_model(
            event_type="person_added",
            user_id=current_user.id,
            actor_name=_sender_name(),
            message=_describe_person(person),
        )
    )
    queue(
        feedback,
        notifications.ADDED,
        user_id=person.user_id,
        actor_id=current_user.id,
        actor_name=_sender_name(),
    )


def _over_hourly_limit(feedback_model: Any, db: Any) -> bool:
    limit = current_app.config.get("MOH_FEEDBACK_MAX_PER_HOUR", DEFAULT_MAX_PER_HOUR)
    sent = (
        db.session.query(feedback_model)
        .filter(
            feedback_model.created_by_fk == current_user.id,
            feedback_model.created_on > _utc_now() - timedelta(hours=1),
        )
        .count()
    )
    return sent >= limit


def _find_submission(feedback_model: Any, db: Any, submission_id: str) -> Any:
    return (
        db.session.query(feedback_model)
        .filter_by(submission_id=submission_id, created_by_fk=current_user.id)
        .one_or_none()
    )


def _sent_response(item: Any) -> Any:
    session[_SENT_REFERENCE_KEY] = item.reference
    if item.target_unit_id and item.first_response_due_on:
        session[_SENT_DUE_KEY] = _deadline_text(item.first_response_due_on)
    return redirect(url_for("moh_feedback.new_feedback"))


def _save_feedback(
    db: Any,
    submission_id: str,
    screenshots: list[StoredScreenshot],
    feedback_type: str,
    message: str,
    unit: OrgUnit | None,
    page_url: str | None,
    direction: str,
    destination: OrgUnit | None,
    people: list[FoundPerson],
) -> Any:
    feedback_model, event_model = _load_models()
    access_model = _load_access_model()
    level_ids = unit.level_ids if unit else (None,) * 7
    feedback = feedback_model(
        submission_id=submission_id,
        created_by_fk=current_user.id,
        sender_name=_sender_name(),
        sender_email=current_user.email,
        sender_role=_sender_role(),
        origin_unit_id=unit.id if unit else None,
        origin_path=unit.path if unit else None,
        direction=direction,
        target_unit_id=destination.id if destination else None,
        target_unit_name=destination.name[:255] if destination else None,
        target_path=destination.path if destination else None,
        type=feedback_type,
        message=message,
        page_url=page_url,
        status="new",
        priority=NORMAL,
        clock_started_on=_utc_now(),
        paused_days=0,
        **{f"origin_level{index}id": value for index, value in enumerate(level_ids, 1)},
    )
    refresh_deadlines(feedback)
    feedback.events.append(
        event_model(
            event_type="created",
            to_status="new",
            user_id=current_user.id,
            actor_name=_sender_name(),
        )
    )
    if destination:
        feedback.unit_access.append(
            access_model(
                unit_id=destination.id,
                unit_name=destination.name[:255],
                reason="target",
                is_current=True,
            )
        )
        feedback.events.append(
            event_model(
                event_type="routed",
                to_unit_id=destination.id,
                message=destination.name,
            )
        )
    else:
        feedback.events.append(event_model(event_type="routing_pending"))
    participant_model = _load_participant_model()
    for person in people:
        _attach_person(feedback, person, participant_model, event_model)
    attachment_model = _load_attachment_model()
    for screenshot in screenshots:
        feedback.attachments.append(
            attachment_model(
                stored_name=screenshot.stored_name,
                original_name=screenshot.original_name,
                content_type=screenshot.content_type,
                size_bytes=screenshot.size_bytes,
            )
        )
    queue(feedback, notifications.RECEIVED, user_id=current_user.id)
    db.session.add(feedback)
    db.session.commit()
    return feedback


def _save_and_confirm(
    db: Any,
    feedback_model: Any,
    submission_id: str,
    screenshots: list[StoredScreenshot],
    *details: Any,
) -> Any:
    """Save the item, treating a simultaneous copy of it as already sent.

    Screenshots are already on disk, so they are removed if the item is not saved.
    """
    try:
        feedback = _save_feedback(db, submission_id, screenshots, *details)
    except IntegrityError:
        attachments.remove_files(screenshots)
        db.session.rollback()
        existing = _find_submission(feedback_model, db, submission_id)
        if existing is None:
            taken = (
                db.session.query(feedback_model.id)
                .filter_by(submission_id=submission_id)
                .first()
            )
            if taken is None:
                raise
            # A form's id only belongs to another user if the form was tampered with
            abort(400)
        return _sent_response(existing)
    except Exception:
        attachments.remove_files(screenshots)
        raise
    return _sent_response(feedback)


def _store_uploaded_screenshots() -> list[StoredScreenshot]:
    try:
        return attachments.store_screenshots(
            attachments.prepare_screenshots(request.files.getlist("screenshots"))
        )
    except attachments.ScreenshotError as problem:
        raise _RouteRefusedError(problem.message, 400) from problem


@moh_feedback_bp.route("/new", methods=["GET"])
def new_feedback() -> Any:
    """Show the feedback form."""
    if not current_app.config.get("MOH_FEEDBACK_ENABLED", False):
        abort(404)
    if not _is_signed_in():
        return redirect(f"/login/?next={request.full_path.rstrip('?')}")
    return _render_form(
        get_user_units(current_user.username),
        page_url=safe_page_url(request.args.get("from")) or _referrer_page(),
    )


@moh_feedback_bp.route("/", methods=["POST"])
def submit_feedback() -> Any:
    """Save one item of feedback from the signed-in user."""
    if not current_app.config.get("MOH_FEEDBACK_ENABLED", False):
        abort(404)
    if not _is_signed_in():
        return redirect("/login/?next=/moh/feedback/new")

    lookup = get_user_units(current_user.username)
    if (request.content_length or 0) > attachments.max_request_bytes():
        return _render_form(
            lookup, 413, "Your screenshots are too large. Please send smaller ones."
        )
    units = selectable_units(lookup or [])
    direction = request.form.get("direction", "up")
    feedback_type = request.form.get("type", "")
    message = clean_message(request.form.get("message", ""))
    unit_id = request.form.get("unit_id", "")
    page_url = safe_page_url(request.form.get("page_url"))
    submission_id = request.form.get("submission_id", "")
    chosen, all_read = _chosen_people()
    people = [person for _, person in chosen]
    values: dict[str, Any] = {
        "type": feedback_type,
        "message": message,
        "unit_id": unit_id,
        "direction": direction,
        "people": [
            {"token": token, "name": person.name, "paths": list(person.paths)}
            for token, person in chosen
        ],
    }

    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        return _render_form(
            lookup,
            400,
            "This page expired. Your message is kept below; please send it again.",
            values,
            page_url,
        )
    if not _SUBMISSION_ID.match(submission_id):
        return _render_form(
            lookup, 400, "Please send the form again.", values, page_url
        )

    db = _load_db()
    feedback_model, _ = _load_models()
    if (existing := _find_submission(feedback_model, db, submission_id)) is not None:
        return _sent_response(existing)

    error = _validation_error(
        feedback_type, message, unit_id, units, direction
    ) or _selection_problem(db, people, all_read)
    if error:
        return _render_form(lookup, 400, error, values, page_url)
    if _over_hourly_limit(feedback_model, db):
        return _render_form(
            lookup,
            429,
            "You have sent a lot of feedback in the last hour. Please try again later.",
            values,
            page_url,
        )

    unit = next((item for item in units if item.id == unit_id), None) or (
        units[0] if units else None
    )
    try:
        destination = _choose_destination(
            direction, unit, lookup, request.form.get("target_unit_id", "")
        )
        screenshots = _store_uploaded_screenshots()
    except _RouteRefusedError as refused:
        return _render_form(lookup, refused.status, refused.message, values, page_url)
    return _save_and_confirm(
        db,
        feedback_model,
        submission_id,
        screenshots,
        feedback_type,
        message,
        unit,
        page_url,
        direction,
        destination,
        people,
    )


@moh_feedback_bp.route("/units", methods=["GET"])
def units_below() -> Any:
    """Search the units below the signed-in user, for sending feedback down."""
    if not current_app.config.get("MOH_FEEDBACK_ENABLED", False):
        abort(404)
    if not _is_signed_in():
        abort(401)

    term = request.args.get("q", "").strip()
    lookup = get_user_units(current_user.username)
    if lookup is None:
        return jsonify(error="unavailable"), 503
    units = selectable_units(lookup)
    origin = next(
        (unit for unit in units if unit.id == request.args.get("unit_id")), None
    ) or (units[0] if len(units) == 1 else None)
    if origin is None or len(term) < UNIT_SEARCH_MIN_LENGTH:
        return jsonify(result=[])
    try:
        options = describe_units_below(
            origin, term, current_user.username, UNIT_SEARCH_LIMIT
        )
    except OrgUnitLookupError:
        return jsonify(error="unavailable"), 503
    return jsonify(
        result=[
            {
                "id": option.unit.id,
                "name": option.unit.name,
                "path": option.unit.path,
                "active_users": option.active_users,
                "goes_to": option.destination.name if option.destination else None,
            }
            for option in options
        ]
    )


def _over_search_limit(db: Any) -> bool:
    """Count this search, returning whether the user has searched too often."""
    search_model = _load_search_model()
    cutoff = _utc_now() - PERSON_SEARCH_WINDOW
    own = db.session.query(search_model).filter(search_model.user_id == current_user.id)
    own.filter(search_model.searched_on <= cutoff).delete(synchronize_session=False)
    limit = current_app.config.get(
        "MOH_FEEDBACK_MAX_PERSON_SEARCHES", DEFAULT_MAX_PERSON_SEARCHES
    )
    over_limit = own.count() >= limit
    if not over_limit:
        db.session.add(search_model(user_id=current_user.id))
    db.session.commit()
    return over_limit


@moh_feedback_bp.route("/people/search", methods=["POST"])
def search_people() -> Any:
    """Find people by exact email, username, or first and last name.

    Sent by POST to keep email addresses out of server access logs. Results
    never include the person's email or username.
    """
    if not current_app.config.get("MOH_FEEDBACK_ENABLED", False):
        abort(404)
    if not _is_signed_in():
        abort(401)
    if not _csrf_is_valid():
        return jsonify(error="expired"), 400

    term = request.form.get("q", "")
    if not is_searchable(term):
        return jsonify(result=[])
    if _over_search_limit(_load_db()):
        return jsonify(error="too_many"), 429
    try:
        people = find_people(term, current_user.id, PERSON_SEARCH_LIMIT)
    except OrgUnitLookupError:
        return jsonify(error="unavailable"), 503
    return jsonify(
        result=[
            {
                "token": person_token(person, current_user.id),
                "name": person.name,
                "paths": list(person.paths),
            }
            for person in people
        ]
    )


def _users_unit_ids() -> set[str]:
    """Return the ids of the signed-in handler's units; raises when unknown.

    The answer is kept for the request, as one page asks more than once.
    """
    if _UNIT_IDS_KEY not in request.environ:
        lookup = get_user_units(current_user.username)
        if lookup is None:
            raise OrgUnitLookupError("org units unavailable")
        request.environ[_UNIT_IDS_KEY] = {unit.id for unit in lookup}
    return request.environ[_UNIT_IDS_KEY]


@dataclass(frozen=True)
class _ItemAccess:
    """What the signed-in user may do with one item."""

    is_sender: bool
    can_read: bool
    can_act: bool
    is_participant: bool = False
    # Internal notes are for the units that have handled the item
    sees_internal: bool = False

    @property
    def can_manage_people(self) -> bool:
        return self.is_sender or self.can_act


def _handling_units(item: Any, is_participant: bool) -> list[Any]:
    """Return the signed-in user's rows among the units that can read the item."""
    if not _can_handle():
        return []
    try:
        unit_ids = _users_unit_ids()
    except OrgUnitLookupError:
        # Unit access is refused rather than guessed while the unit is unknown
        if is_participant:
            return []
        abort(503)
    return [row for row in item.unit_access if row.unit_id in unit_ids]


def _item_access(item: Any) -> _ItemAccess:
    """Work out access from the sender, added people, and the item's units."""
    if item.created_by_fk == current_user.id:
        return _ItemAccess(is_sender=True, can_read=True, can_act=False)
    is_participant = any(
        row.user_id == current_user.id for row in item.active_participants
    )
    ours = _handling_units(item, is_participant)
    return _ItemAccess(
        is_sender=False,
        can_read=bool(ours) or is_participant,
        can_act=any(row.is_current for row in ours),
        is_participant=is_participant,
        sees_internal=bool(ours),
    )


def _current_actor() -> Person:
    return Person(current_user.id, _sender_name())


def _responsible_unit_id(item: Any) -> str | None:
    return responsible_unit_id(item)


def _assignable_people(item: Any) -> list[Person]:
    """List who the item can be assigned to; never the person who sent it."""
    unit_id = _responsible_unit_id(item)
    if unit_id is None:
        return []
    try:
        return unit_handlers(unit_id, item.created_by_fk)
    except OrgUnitLookupError:
        return []


@dataclass(frozen=True)
class _MoveOptions:
    """Where a responsible unit can pass an item on to."""

    responsible_id: str
    up_name: str | None
    can_move_down: bool


def _item_sender_username(item: Any) -> str:
    return sender_username(item, _load_db())


def _move_options(item: Any) -> _MoveOptions | None:
    """Work out what to offer; an unknown org unit offers no destinations."""
    unit_id = _responsible_unit_id(item)
    if unit_id is None:
        return None
    unavailable = _MoveOptions(unit_id, None, False)
    try:
        unit = get_units([unit_id]).get(unit_id)
        if unit is None:
            return unavailable
        above = find_destination_up(unit, _item_sender_username(item))
    except OrgUnitLookupError:
        return unavailable
    up_name = above.name if above and above.id != unit_id else None
    return _MoveOptions(unit_id, up_name, not unit.leaf)


def _render_detail(
    item: Any,
    access: _ItemAccess,
    status: int = 200,
    error: str | None = None,
    draft: str = "",
) -> tuple[str, int]:
    db = _load_db()
    _, event_model = _load_models()
    history = db.session.query(event_model).filter_by(feedback_id=item.id)
    if not access.sees_internal:
        history = history.filter(~event_model.is_internal)
    actions = allowed_actions(item.status) if access.can_act else set()
    can_move = access.can_act and item.status in MOVE_ACTION.from_statuses
    html = render_template(
        "moh_feedback/detail.html",
        item=item,
        is_sender=access.is_sender,
        sees_internal=access.sees_internal,
        participants=item.active_participants,
        can_add_people=access.can_manage_people and item.status != CLOSED,
        can_remove_people=access.can_manage_people,
        current_user_id=current_user.id,
        participant_can_comment=(
            access.is_participant and not access.can_act and item.status != CLOSED
        ),
        max_people=_max_people_per_item(),
        move_options=_move_options(item) if can_move else None,
        priorities=PRIORITIES,
        events=history.order_by(event_model.created_on, event_model.id).all(),
        actions=actions,
        assignable_people=_assignable_people(item) if ASSIGN in actions else [],
        sender_can_reply=access.is_sender and item.status == NEEDS_INFO,
        sender_can_add=access.is_sender and item.status in _SENDER_CAN_ADD,
        sender_can_reopen=access.is_sender and _within_reopen_window(item),
        reopen_days=_reopen_days(),
        can_hide=access.can_act,
        page_label=_page_title(item.page_url) if item.page_url else None,
        sender_can_confirm=access.is_sender and item.status == ANSWERED,
        message_max_length=MESSAGE_MAX_LENGTH,
        error=error,
        draft=draft,
        csrf_token=generate_csrf(),
        type_labels=dict(FEEDBACK_TYPES),
        status_labels=STATUS_LABELS,
        event_labels=EVENT_LABELS,
    )
    return html, status


def _lock_item(db: Any, item_id: int) -> Any:
    """Reload an item and hold its row until commit, so changes cannot overlap."""
    feedback_model, _ = _load_models()
    return (
        db.session.query(feedback_model)
        .filter_by(id=item_id)
        .populate_existing()
        .with_for_update()
        .one()
    )


def _item_or_404(db: Any, feedback_uuid: uuid.UUID) -> Any:
    feedback_model, _ = _load_models()
    item = db.session.query(feedback_model).filter_by(uuid=feedback_uuid).one_or_none()
    if item is None:
        abort(404)
    return item


def _csrf_is_valid() -> bool:
    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        return False
    return True


@moh_feedback_bp.route("/waiting", methods=["GET"])
def waiting_on_me() -> Any:
    """List the feedback the signed-in user's unit is responsible for, oldest first."""
    if not current_app.config.get("MOH_FEEDBACK_ENABLED", False):
        abort(404)
    if not _is_signed_in():
        return redirect(f"/login/?next={request.full_path.rstrip('?')}")
    if not _can_handle():
        abort(404)

    try:
        unit_ids = _users_unit_ids()
    except OrgUnitLookupError:
        return render_template("moh_feedback/waiting.html", unavailable=True), 503

    db = _load_db()
    feedback_model, _ = _load_models()
    show_all = request.args.get("view") == "all"
    waiting = _items_at_units(db, unit_ids)
    if not show_all:
        waiting = waiting.filter(_needs_action_filter(feedback_model))
    waiting, filters = _apply_filters(waiting, feedback_model, show_all)
    items, page, pages = _paged(
        waiting,
        feedback_model.due_on.asc().nullslast(),
        feedback_model.created_on.asc(),
        feedback_model.id.asc(),
    )
    return render_template(
        "moh_feedback/waiting.html",
        unavailable=False,
        show_all=show_all,
        items=items,
        filters=filters,
        status_filters=_status_filter_options(show_all),
        page=page,
        pages=pages,
        type_labels=dict(FEEDBACK_TYPES),
        status_labels=STATUS_LABELS,
    )


@moh_feedback_bp.route("/mine", methods=["GET"])
def my_feedback() -> Any:
    """List the signed-in user's own feedback, newest first."""
    if not current_app.config.get("MOH_FEEDBACK_ENABLED", False):
        abort(404)
    if not _is_signed_in():
        return redirect(f"/login/?next={request.full_path.rstrip('?')}")

    db = _load_db()
    feedback_model, _ = _load_models()
    show_added = request.args.get("view") == "added"
    if show_added:
        participant_model = _load_participant_model()
        listed = (
            db.session.query(feedback_model)
            .join(participant_model, participant_model.feedback_id == feedback_model.id)
            .filter(
                participant_model.user_id == current_user.id,
                participant_model.removed_on.is_(None),
            )
        )
    else:
        listed = db.session.query(feedback_model).filter(
            feedback_model.created_by_fk == current_user.id
        )
    listed, filters = _apply_filters(listed, feedback_model, True)
    needs_sender_first = case((feedback_model.status.in_(_NEEDS_SENDER), 0), else_=1)
    items, page, pages = _paged(
        listed,
        *([] if show_added else [needs_sender_first]),
        feedback_model.created_on.desc(),
        feedback_model.id.desc(),
    )
    return render_template(
        "moh_feedback/mine.html",
        view="added" if show_added else None,
        items=items,
        filters=filters,
        status_filters=_status_filter_options(True),
        page=page,
        pages=pages,
        type_labels=dict(FEEDBACK_TYPES),
        status_labels=STATUS_LABELS,
    )


def _status_filter_options(include_all: bool) -> list[tuple[str, str]]:
    """List the choices of the status filter on a page of items."""
    options = [(status, STATUS_LABELS[status]) for status in _FILTER_STATUSES]
    if not include_all:
        options = [
            (s, label) for s, label in options if s in (NEW, IN_REVIEW, ASSIGNED)
        ]
    return [*options, (_OVERDUE_FILTER, "Overdue")]


def _apply_filters(
    query: Any, feedback_model: Any, include_all: bool
) -> tuple[Any, dict[str, str]]:
    """Apply the search box and status filter, returning them for the page links."""
    filters: dict[str, str] = {}
    # Postgres cannot compare text holding the null character
    term = request.args.get("q", "").replace("\x00", "").strip()
    if term := term[:_SEARCH_MAX_LENGTH]:
        filters["q"] = term
        pattern = "%{}%".format(
            term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        conditions = [
            and_(
                feedback_model.message.ilike(pattern, escape="\\"),
                feedback_model.hidden_on.is_(None),
            ),
            feedback_model.sender_name.ilike(pattern, escape="\\"),
            feedback_model.origin_path.ilike(pattern, escape="\\"),
            feedback_model.target_unit_name.ilike(pattern, escape="\\"),
        ]
        if match := _REFERENCE_SEARCH.match(term):
            conditions.append(feedback_model.id == int(match.group(1)))
        query = query.filter(or_(*conditions))
    status = request.args.get("status", "")
    if status == _OVERDUE_FILTER:
        filters["status"] = status
        query = query.filter(overdue_condition(feedback_model, _utc_now()))
    elif status in dict(_status_filter_options(include_all)):
        filters["status"] = status
        query = query.filter(feedback_model.status == status)
    return query, filters


def _reopen_days() -> int:
    return current_app.config.get("MOH_FEEDBACK_REOPEN_DAYS", DEFAULT_REOPEN_DAYS)


def _within_reopen_window(item: Any) -> bool:
    return (
        item.status in REOPEN_ACTION.from_statuses
        and item.closed_on is not None
        and _utc_now() - item.closed_on <= timedelta(days=_reopen_days())
    )


@moh_feedback_bp.route("/attachment/<uuid:attachment_uuid>", methods=["GET"])
def feedback_attachment(attachment_uuid: uuid.UUID) -> Any:
    """Show a screenshot to the people who can read its item."""
    if not current_app.config.get("MOH_FEEDBACK_ENABLED", False):
        abort(404)
    if not _is_signed_in():
        return redirect("/login/")

    row = (
        _load_db()
        .session.query(_load_attachment_model())
        .filter_by(uuid=attachment_uuid)
        .one_or_none()
    )
    if row is None or row.hidden_on or not _item_access(row.feedback).can_read:
        abort(404)
    path = attachments.file_path(row.stored_name)
    if not path.is_file():
        abort(404)
    response = send_file(path, mimetype=row.content_type, conditional=False)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _items_in_area(db: Any, area_ids: set[str], since: datetime) -> list[Any]:
    """Return the items sent from or to an area since a date."""
    feedback_model, _ = _load_models()
    recent = (
        db.session.query(feedback_model)
        .filter(feedback_model.created_on >= since)
        .all()
    )
    target_ids = {item.target_unit_id for item in recent if item.target_unit_id}
    target_units = get_units(target_ids)
    return [item for item in recent if in_area(item, area_ids, target_units)]


def _reopened_item_ids(db: Any, items: list[Any]) -> set[int]:
    if not items:
        return set()
    _, event_model = _load_models()
    rows = (
        db.session.query(event_model.feedback_id)
        .filter(
            event_model.event_type == "sender_not_solved",
            event_model.feedback_id.in_([item.id for item in items]),
        )
        .distinct()
    )
    return {row[0] for row in rows}


@moh_feedback_bp.route("/stats", methods=["GET"])
def area_numbers() -> Any:
    """Show counts for the signed-in handler's area, and never any messages."""
    if not current_app.config.get("MOH_FEEDBACK_ENABLED", False):
        abort(404)
    if not _is_signed_in():
        return redirect(f"/login/?next={request.full_path.rstrip('?')}")
    if not _can_handle():
        abort(404)

    days = request.args.get("days", DEFAULT_STATS_DAYS, type=int)
    if days not in STATS_DAY_OPTIONS:
        days = DEFAULT_STATS_DAYS
    db = _load_db()
    lookup = get_user_units(current_user.username)
    try:
        if lookup is None:
            raise OrgUnitLookupError("org units unavailable")
        now = _utc_now()
        items = _items_in_area(
            db, {unit.id for unit in lookup}, now - timedelta(days=days)
        )
    except OrgUnitLookupError:
        return render_template("moh_feedback/stats.html", unavailable=True), 503
    numbers = summarise(items, _reopened_item_ids(db, items), dict(FEEDBACK_TYPES), now)
    return render_template(
        "moh_feedback/stats.html",
        unavailable=False,
        numbers=numbers,
        area_paths=[unit.path for unit in selectable_units(lookup)],
        days=days,
        day_options=STATS_DAY_OPTIONS,
    )


@moh_feedback_bp.route("/<uuid:feedback_uuid>", methods=["GET"])
def feedback_detail(feedback_uuid: uuid.UUID) -> Any:
    """Show one item to its sender; to anyone else it does not exist."""
    if not current_app.config.get("MOH_FEEDBACK_ENABLED", False):
        abort(404)
    if not _is_signed_in():
        return redirect(f"/login/?next={request.full_path.rstrip('?')}")

    item = _item_or_404(_load_db(), feedback_uuid)
    access = _item_access(item)
    if not access.can_read:
        abort(404)
    return _render_detail(item, access)


def _notify_action(item: Any, name: str, assignee: Person | None) -> None:
    """Queue the email a handler's action calls for."""
    actor = _current_actor()
    if name == ASSIGN and assignee is not None:
        queue(
            item,
            notifications.ASSIGNED,
            user_id=assignee.id,
            actor_id=actor.id,
            actor_name=actor.name,
        )
    if name in _SENDER_EMAILS:
        queue(
            item,
            _SENDER_EMAILS[name],
            user_id=item.created_by_fk,
            actor_id=actor.id,
            actor_name=actor.name,
        )


def _action_problem(
    item: Any, name: str, message: str, unit_before: str | None
) -> tuple[int, str] | None:
    """Return why a handler's action cannot be applied, or None if it can."""
    if name not in ACTIONS:
        return 400, "Choose an action."
    if (
        request.form.get("expected_status") != item.status
        or name not in allowed_actions(item.status)
        or _responsible_unit_id(item) != unit_before
    ):
        return 409, "This item has changed. Please check it and try again."
    if name == SET_PRIORITY and request.form.get("priority") not in PRIORITIES:
        return 400, "Choose a priority."
    if ACTIONS[name].needs_message and not message:
        return 400, "Please write a message."
    if len(message) > MESSAGE_MAX_LENGTH:
        return 400, f"Please keep your message under {MESSAGE_MAX_LENGTH:,} characters."
    return None


@moh_feedback_bp.route("/<uuid:feedback_uuid>/action", methods=["POST"])
def act_on_feedback(feedback_uuid: uuid.UUID) -> Any:
    """Apply a handler's action to an item."""
    if not current_app.config.get("MOH_FEEDBACK_ENABLED", False):
        abort(404)
    if not _is_signed_in():
        return redirect("/login/")

    db = _load_db()
    item = _item_or_404(db, feedback_uuid)
    access = _item_access(item)
    if not access.can_read:
        abort(404)
    if not access.can_act:
        abort(403)
    message = clean_message(request.form.get("message", ""))
    if not _csrf_is_valid():
        return _render_detail(
            item, access, 400, "This page expired. Please try again.", message
        )

    name = request.form.get("action", "")
    assignee = None
    if name == ASSIGN:
        people = _assignable_people(item)
        assignee = next(
            (p for p in people if str(p.id) == request.form.get("assignee_id")), None
        )
        if assignee is None:
            return _render_detail(
                item, access, 400, "Choose someone to assign.", message
            )

    unit_before = _responsible_unit_id(item)
    item = _lock_item(db, item.id)
    if problem := _action_problem(item, name, message, unit_before):
        db.session.rollback()
        status, text = problem
        return _render_detail(item, access, status, text, message)

    _, event_model = _load_models()
    apply_action(
        item,
        name,
        _current_actor(),
        event_model,
        _utc_now(),
        message or None,
        assignee,
        request.form.get("priority"),
    )
    _notify_action(item, name, assignee)
    db.session.commit()
    return redirect(url_for("moh_feedback.feedback_detail", feedback_uuid=item.uuid))


@moh_feedback_bp.route("/<uuid:feedback_uuid>/reply", methods=["POST"])
def reply_to_feedback(feedback_uuid: uuid.UUID) -> Any:
    """Record a sender's reply to a question, or an added person's comment."""
    if not current_app.config.get("MOH_FEEDBACK_ENABLED", False):
        abort(404)
    if not _is_signed_in():
        return redirect("/login/")

    db = _load_db()
    item = _item_or_404(db, feedback_uuid)
    access = _item_access(item)
    if not (access.is_sender or access.is_participant):
        abort(404)
    message = clean_message(request.form.get("message", ""))
    if not _csrf_is_valid():
        return _render_detail(
            item, access, 400, "This page expired. Please try again.", message
        )
    if not message or len(message) > MESSAGE_MAX_LENGTH:
        return _render_detail(
            item,
            access,
            400,
            f"Please write a reply of up to {MESSAGE_MAX_LENGTH:,} characters.",
            message,
        )

    item = _lock_item(db, item.id)
    allowed = (
        (NEEDS_INFO, *_SENDER_CAN_ADD)
        if access.is_sender
        else (*_SENDER_CAN_ADD, NEEDS_INFO, ANSWERED)
    )
    if item.status not in allowed:
        db.session.rollback()
        return _render_detail(
            item, access, 409, "This item has changed. Please check it.", message
        )
    _, event_model = _load_models()
    if access.is_sender and item.status == NEEDS_INFO:
        apply_sender_reply(item, _current_actor(), event_model, message, _utc_now())
        notify_handlers(
            item, notifications.REPLIED, current_user.id, _responsible_unit_id(item)
        )
    elif access.is_sender:
        apply_sender_message(item, _current_actor(), event_model, message)
        notify_handlers(
            item,
            notifications.SENDER_MESSAGE,
            current_user.id,
            _responsible_unit_id(item),
        )
    else:
        apply_participant_comment(item, _current_actor(), event_model, message)
    db.session.commit()
    return redirect(url_for("moh_feedback.feedback_detail", feedback_uuid=item.uuid))


def _decision_problem(decision: str, message: str) -> str | None:
    """Return why the sender's decision cannot be accepted, or None if it can."""
    if decision not in (SOLVED, NOT_SOLVED):
        return "Please choose whether this solved it."
    if decision == NOT_SOLVED and not message:
        return "Please say why this is not solved."
    if len(message) > MESSAGE_MAX_LENGTH:
        return f"Please keep your message under {MESSAGE_MAX_LENGTH:,} characters."
    return None


@moh_feedback_bp.route("/<uuid:feedback_uuid>/confirm", methods=["POST"])
def confirm_feedback(feedback_uuid: uuid.UUID) -> Any:
    """Record whether the answer solved the sender's problem."""
    if not current_app.config.get("MOH_FEEDBACK_ENABLED", False):
        abort(404)
    if not _is_signed_in():
        return redirect("/login/")

    db = _load_db()
    item = _item_or_404(db, feedback_uuid)
    access = _item_access(item)
    if not access.is_sender:
        abort(404)
    message = clean_message(request.form.get("message", ""))
    if not _csrf_is_valid():
        return _render_detail(
            item, access, 400, "This page expired. Please try again.", message
        )
    decision = request.form.get("decision", "")
    if problem := _decision_problem(decision, message):
        return _render_detail(item, access, 400, problem, message)

    item = _lock_item(db, item.id)
    if item.status != ANSWERED:
        db.session.rollback()
        return _render_detail(
            item, access, 409, "This item has changed. Please check it.", message
        )
    _, event_model = _load_models()
    apply_sender_decision(
        item,
        decision == SOLVED,
        _current_actor(),
        event_model,
        _utc_now(),
        message or None,
    )
    if decision == NOT_SOLVED:
        notify_handlers(
            item, notifications.NOT_SOLVED, current_user.id, _responsible_unit_id(item)
        )
    db.session.commit()
    return redirect(url_for("moh_feedback.feedback_detail", feedback_uuid=item.uuid))


def _add_problem(db: Any, item: Any, person: FoundPerson) -> tuple[int, str] | None:
    """Return why this person cannot be added to the item, or None if they can."""
    if item.status == CLOSED:
        return 409, "This item is closed."
    if person.user_id == item.created_by_fk:
        return 400, "This person sent this feedback."
    active = item.active_participants
    if any(row.user_id == person.user_id for row in active):
        return 409, "This person is already added."
    if problem := _people_problem(db, [person], len(active)):
        return 400, problem
    return None


@moh_feedback_bp.route("/<uuid:feedback_uuid>/participants", methods=["POST"])
def add_participant(feedback_uuid: uuid.UUID) -> Any:
    """Add a person to an existing item."""
    if not current_app.config.get("MOH_FEEDBACK_ENABLED", False):
        abort(404)
    if not _is_signed_in():
        return redirect("/login/")

    db = _load_db()
    item = _item_or_404(db, feedback_uuid)
    access = _item_access(item)
    if not access.can_read:
        abort(404)
    if not access.can_manage_people:
        abort(403)
    if not _csrf_is_valid():
        return _render_detail(item, access, 400, "This page expired. Please try again.")
    person = read_person_token(request.form.get("person_token", ""), current_user.id)
    if person is None:
        return _render_detail(item, access, 400, "Please search for the person again.")

    unit_before = _responsible_unit_id(item)
    item = _lock_item(db, item.id)
    if not access.is_sender and _responsible_unit_id(item) != unit_before:
        db.session.rollback()
        return _render_detail(item, access, 409, "This item has changed.")
    if problem := _add_problem(db, item, person):
        db.session.rollback()
        status, text = problem
        return _render_detail(item, access, status, text)
    _, event_model = _load_models()
    _attach_person(item, person, _load_participant_model(), event_model)
    db.session.commit()
    return redirect(url_for("moh_feedback.feedback_detail", feedback_uuid=item.uuid))


@moh_feedback_bp.route("/<uuid:feedback_uuid>/participants/remove", methods=["POST"])
def remove_participant(feedback_uuid: uuid.UUID) -> Any:
    """Remove a person from an item, or let them remove themselves."""
    if not current_app.config.get("MOH_FEEDBACK_ENABLED", False):
        abort(404)
    if not _is_signed_in():
        return redirect("/login/")

    db = _load_db()
    item = _item_or_404(db, feedback_uuid)
    access = _item_access(item)
    if not access.can_read:
        abort(404)
    if not _csrf_is_valid():
        return _render_detail(item, access, 400, "This page expired. Please try again.")

    item = _lock_item(db, item.id)
    wanted = request.form.get("participant_id")
    row = next((p for p in item.active_participants if str(p.id) == wanted), None)
    if row is None:
        db.session.rollback()
        return _render_detail(item, access, 409, "This person is no longer added.")
    removing_self = row.user_id == current_user.id
    if not (removing_self or access.can_manage_people):
        db.session.rollback()
        abort(403)
    row.removed_on = _utc_now()
    row.removed_by_fk = current_user.id
    _, event_model = _load_models()
    item.events.append(
        event_model(
            event_type="person_removed",
            user_id=current_user.id,
            actor_name=_sender_name(),
            message=row.display_name,
        )
    )
    db.session.commit()
    if removing_self and not access.sees_internal:
        return redirect(url_for("moh_feedback.my_feedback", view="added"))
    return redirect(url_for("moh_feedback.feedback_detail", feedback_uuid=item.uuid))


def _move_destination(item: Any, direction: str, target_unit_id: str) -> OrgUnit:
    """Return the unit an item is being passed to, or say why it cannot go there."""
    unit_id = _responsible_unit_id(item) or ""
    unavailable = "We cannot check the org units right now. Please try again."
    try:
        current = get_units([unit_id]).get(unit_id)
        if current is None:
            raise _RouteRefusedError(unavailable, 503)
        sender = _item_sender_username(item)
        if direction == "up":
            above = find_destination_up(current, sender)
            if above is None or above.id == current.id:
                raise _RouteRefusedError(
                    "There is no level above that can receive this.", 400
                )
            return above
        target = get_units([target_unit_id]).get(target_unit_id)
        if target is None or target.closed or not is_below(current, target):
            raise _RouteRefusedError("Choose a unit below yours.", 400)
        destination = find_destination_down(current, target, sender)
    except OrgUnitLookupError as ex:
        raise _RouteRefusedError(unavailable, 503) from ex
    if destination is None:
        raise _RouteRefusedError(
            "No active user can receive feedback for that unit. Choose another unit.",
            400,
        )
    return destination


def _move_input_problem(direction: str, reason: str) -> str | None:
    if direction not in DIRECTIONS:
        return "Choose where to pass this on to."
    if not reason:
        return "Please write why you are passing this on."
    if len(reason) > MESSAGE_MAX_LENGTH:
        return f"Please keep your reason under {MESSAGE_MAX_LENGTH:,} characters."
    return None


@moh_feedback_bp.route("/<uuid:feedback_uuid>/move", methods=["POST"])
def move_feedback(feedback_uuid: uuid.UUID) -> Any:
    """Pass an item to the level above or to a unit below the responsible one."""
    if not current_app.config.get("MOH_FEEDBACK_ENABLED", False):
        abort(404)
    if not _is_signed_in():
        return redirect("/login/")

    db = _load_db()
    item = _item_or_404(db, feedback_uuid)
    access = _item_access(item)
    if not access.can_read:
        abort(404)
    if not access.can_act:
        abort(403)
    reason = clean_message(request.form.get("reason", ""))
    if not _csrf_is_valid():
        return _render_detail(item, access, 400, "This page expired. Please try again.")
    direction = request.form.get("direction", "")
    if problem := _move_input_problem(direction, reason):
        return _render_detail(item, access, 400, problem)
    try:
        destination = _move_destination(
            item, direction, request.form.get("target_unit_id", "")
        )
    except _RouteRefusedError as refused:
        return _render_detail(item, access, refused.status, refused.message)

    unit_before = _responsible_unit_id(item)
    item = _lock_item(db, item.id)
    if (
        request.form.get("expected_status") != item.status
        or item.status not in MOVE_ACTION.from_statuses
        or _responsible_unit_id(item) != unit_before
    ):
        db.session.rollback()
        return _render_detail(
            item, access, 409, "This item has changed. Please check it and try again."
        )
    _, event_model = _load_models()
    hand_over(
        db,
        (event_model, _load_access_model()),
        item,
        destination,
        _current_actor(),
        reason,
        _utc_now(),
    )
    db.session.commit()
    return redirect(url_for("moh_feedback.feedback_detail", feedback_uuid=item.uuid))


@moh_feedback_bp.route("/<uuid:feedback_uuid>/reopen", methods=["POST"])
def reopen_feedback(feedback_uuid: uuid.UUID) -> Any:
    """Let the sender reopen a recently closed item, saying why."""
    if not current_app.config.get("MOH_FEEDBACK_ENABLED", False):
        abort(404)
    if not _is_signed_in():
        return redirect("/login/")

    db = _load_db()
    item = _item_or_404(db, feedback_uuid)
    access = _item_access(item)
    if not access.is_sender:
        abort(404)
    message = clean_message(request.form.get("message", ""))
    if not _csrf_is_valid():
        return _render_detail(
            item, access, 400, "This page expired. Please try again.", message
        )
    if not message or len(message) > MESSAGE_MAX_LENGTH:
        return _render_detail(
            item, access, 400, "Please say why you are reopening this.", message
        )

    item = _lock_item(db, item.id)
    if not _within_reopen_window(item):
        db.session.rollback()
        return _render_detail(
            item, access, 409, "This item can no longer be reopened.", message
        )
    _, event_model = _load_models()
    apply_reopen(item, _current_actor(), event_model, _utc_now(), message)
    notify_handlers(
        item, notifications.REOPENED, current_user.id, _responsible_unit_id(item)
    )
    db.session.commit()
    return redirect(url_for("moh_feedback.feedback_detail", feedback_uuid=item.uuid))


def _hide_target(item: Any, target: str) -> tuple[Any, str] | None:
    """Return what a hide request refers to on this item, and how to describe it."""
    kind, _, raw_id = target.partition("-")
    if kind == "message" and not raw_id:
        return item, _HIDDEN_LABELS["message"]
    rows = {"event": item.events, "attachment": item.attachments}.get(kind)
    found = next((row for row in rows or [] if str(row.id) == raw_id), None)
    if found is None or (kind == "event" and not found.message):
        return None
    return found, _HIDDEN_LABELS.get(kind, "A screenshot")


@moh_feedback_bp.route("/<uuid:feedback_uuid>/hide", methods=["POST"])
def hide_content(feedback_uuid: uuid.UUID) -> Any:
    """Hide a message or screenshot that holds patient details, for everyone."""
    if not current_app.config.get("MOH_FEEDBACK_ENABLED", False):
        abort(404)
    if not _is_signed_in():
        return redirect("/login/")

    db = _load_db()
    item = _item_or_404(db, feedback_uuid)
    access = _item_access(item)
    if not access.can_read:
        abort(404)
    if not access.can_act:
        abort(403)
    if not _csrf_is_valid():
        return _render_detail(item, access, 400, "This page expired. Please try again.")

    item = _lock_item(db, item.id)
    found = _hide_target(item, request.form.get("target", ""))
    if found is None or found[0].hidden_on is not None:
        db.session.rollback()
        return _render_detail(item, access, 409, "This has changed. Please check it.")
    target, description = found
    target.hidden_on = _utc_now()
    _, event_model = _load_models()
    item.events.append(
        event_model(
            event_type="content_hidden",
            user_id=current_user.id,
            actor_name=_sender_name(),
            message=description,
        )
    )
    db.session.commit()
    return redirect(url_for("moh_feedback.feedback_detail", feedback_uuid=item.uuid))
