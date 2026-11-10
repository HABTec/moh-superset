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
"""Background jobs of the feedback loop.

The jobs that change items only run if ``MOH_FEEDBACK_AUTOMATION_ENABLED`` is set.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from celery import Task
from flask import current_app
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from superset.extensions import celery_app
from superset.moh_feedback.handover import (
    hand_over,
    responsible_unit_id,
    sender_username,
)
from superset.moh_feedback.notifications import (
    auto_close_days,
    AUTO_CLOSED,
    deliver_due,
    DIGEST,
    emails_enabled,
    PENDING,
    queue,
)
from superset.moh_feedback.org_units import (
    get_units,
    get_user_units,
    OrgUnit,
    OrgUnitLookupError,
    selectable_units,
)
from superset.moh_feedback.routing import (
    find_destination_up,
    find_escalation_target,
    unit_handlers,
)
from superset.moh_feedback.workflow import (
    ANSWERED,
    apply_auto_close,
    ASSIGNED,
    IN_REVIEW,
    is_overdue,
    NEEDS_INFO,
    NEW,
    overdue_condition,
    Person,
)
from superset.utils import json

logger = logging.getLogger(__name__)

_SYSTEM = Person(None, "System")
_BEING_HANDLED = (NEW, IN_REVIEW, ASSIGNED)
OVERDUE_REASON = "Overdue, so it was passed on automatically."


def _load_db() -> Any:
    from superset.extensions import db  # pylint: disable=import-outside-toplevel

    return db


def _models() -> tuple[Any, Any, Any, Any]:
    # pylint: disable=import-outside-toplevel
    from superset.models.moh_feedback import (
        MohFeedback,
        MohFeedbackEvent,
        MohFeedbackNotification,
        MohFeedbackUnitAccess,
    )

    return (
        MohFeedback,
        MohFeedbackEvent,
        MohFeedbackUnitAccess,
        MohFeedbackNotification,
    )


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


def _automation_enabled() -> bool:
    return bool(current_app.config.get("MOH_FEEDBACK_AUTOMATION_ENABLED", False))


def _locked(db: Any, feedback_model: Any, item_id: int) -> Any:
    """Reload an item and hold its row, or None if another job holds it."""
    return (
        db.session.query(feedback_model)
        .filter_by(id=item_id)
        .populate_existing()
        .with_for_update(skip_locked=True)
        .one_or_none()
    )


def queue_daily_digest(db: Any, now: datetime | None = None) -> None:
    """Queue one summary for each handler who has new or overdue items."""
    moment = now or _utc_now()
    feedback_model, _, access_model, notification_model = _models()
    rows = (
        db.session.query(feedback_model, access_model.unit_id)
        .join(access_model, access_model.feedback_id == feedback_model.id)
        .filter(access_model.is_current, feedback_model.status.in_(_BEING_HANDLED))
        .all()
    )
    by_unit: dict[str, list[Any]] = defaultdict(list)
    for item, unit_id in rows:
        if item.status == NEW or is_overdue(item, moment):
            by_unit[unit_id].append(item)

    totals: dict[int, dict[str, int]] = {}
    for unit_id, items in by_unit.items():
        try:
            people = unit_handlers(unit_id, None)
        except OrgUnitLookupError:
            logger.warning("Feedback summary skipped: org units unavailable")
            db.session.rollback()
            return
        for person in people:
            for item in items:
                if person.id is None or item.created_by_fk == person.id:
                    continue
                counts = totals.setdefault(person.id, {"new": 0, "overdue": 0})
                counts["new"] += item.status == NEW
                counts["overdue"] += is_overdue(item, moment)

    day = moment.date().isoformat()
    for user_id, counts in totals.items():
        db.session.add(
            notification_model(
                user_id=user_id,
                kind=DIGEST,
                detail=json.dumps(counts),
                dedupe_key=f"digest:{day}:{user_id}",
                status=PENDING,
                next_attempt_on=moment,
            )
        )
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()


def auto_close_items(db: Any, now: datetime | None = None) -> int:
    """Close items that have waited on the sender too long; returns how many."""
    moment = now or _utc_now()
    feedback_model, event_model, _, _ = _models()
    cutoff = moment - timedelta(days=auto_close_days())
    waiting_since = func.coalesce(feedback_model.paused_on, feedback_model.changed_on)
    item_ids = [
        row[0]
        for row in db.session.query(feedback_model.id)
        .filter(
            feedback_model.status.in_((ANSWERED, NEEDS_INFO)),
            waiting_since <= cutoff,
        )
        .all()
    ]
    db.session.rollback()
    closed = 0
    for item_id in item_ids:
        item = _locked(db, feedback_model, item_id)
        if item is None or item.status not in (ANSWERED, NEEDS_INFO):
            db.session.rollback()
            continue
        apply_auto_close(item, _SYSTEM, event_model, moment)
        queue(item, AUTO_CLOSED, user_id=item.created_by_fk)
        db.session.commit()
        closed += 1
    return closed


def _escalation_target(db: Any, item: Any) -> tuple[OrgUnit, OrgUnit | None] | None:
    """Return the responsible unit and where an overdue item should go."""
    unit_id = responsible_unit_id(item)
    if unit_id is None:
        return None
    current = get_units([unit_id]).get(unit_id)
    if current is None:
        return None
    target = find_escalation_target(
        current, sender_username(item, db), item.direction, item.origin_unit_id
    )
    return current, target


def _overdue_item_ids(db: Any, feedback_model: Any, moment: datetime) -> list[int]:
    return [
        row[0]
        for row in db.session.query(feedback_model.id)
        .filter(
            overdue_condition(feedback_model, moment),
        )
        .all()
    ]


def escalate_overdue_items(db: Any, now: datetime | None = None) -> int:
    """Pass overdue items to the next level with a handler; returns how many."""
    moment = now or _utc_now()
    feedback_model, event_model, access_model, _ = _models()
    item_ids = _overdue_item_ids(db, feedback_model, moment)
    db.session.rollback()
    moved = 0
    for item_id in item_ids:
        item = _locked(db, feedback_model, item_id)
        if item is None or not is_overdue(item, moment):
            db.session.rollback()
            continue
        try:
            found = _escalation_target(db, item)
        except OrgUnitLookupError:
            logger.warning("Feedback escalation stopped: org units unavailable")
            db.session.rollback()
            return moved
        if found is None or found[1] is None or found[1].id == found[0].id:
            db.session.rollback()
            continue
        hand_over(
            db,
            (event_model, access_model),
            item,
            found[1],
            _SYSTEM,
            OVERDUE_REASON,
            moment,
            access_reason="escalated",
        )
        db.session.commit()
        moved += 1
    return moved


def _route_one(db: Any, models: tuple[Any, Any, Any], item: Any) -> bool:
    """Route one item saved without a destination; False if units are unknown."""
    _, event_model, access_model = models
    username = sender_username(item, db)
    lookup = get_user_units(username)
    if lookup is None:
        return False
    units = selectable_units(lookup)
    origin = units[0] if units else None
    if item.origin_unit_id is None and origin is not None:
        item.origin_unit_id = origin.id
        item.origin_path = origin.path
        for index, value in enumerate(origin.level_ids, 1):
            setattr(item, f"origin_level{index}id", value)
    destination = find_destination_up(origin, username)
    if destination is None:
        return True
    item.target_unit_id = destination.id
    item.target_unit_name = destination.name[:255]
    item.target_path = destination.path
    item.unit_access.append(
        access_model(
            unit_id=destination.id,
            unit_name=destination.name[:255],
            reason="target",
            is_current=True,
        )
    )
    item.events.append(
        event_model(
            event_type="routed", to_unit_id=destination.id, message=destination.name
        )
    )
    return True


def route_pending_items(db: Any) -> int:
    """Route items saved while org units were unavailable; returns how many."""
    feedback_model, event_model, access_model, _ = _models()
    item_ids = [
        row[0]
        for row in db.session.query(feedback_model.id)
        .filter(feedback_model.target_unit_id.is_(None), feedback_model.status == NEW)
        .all()
    ]
    db.session.rollback()
    routed = 0
    for item_id in item_ids:
        item = _locked(db, feedback_model, item_id)
        if item is None or item.target_unit_id is not None:
            db.session.rollback()
            continue
        try:
            known = _route_one(db, (feedback_model, event_model, access_model), item)
        except OrgUnitLookupError:
            known = False
        if not known:
            db.session.rollback()
            return routed
        routed += item.target_unit_id is not None
        db.session.commit()
    return routed


@celery_app.task(name="moh_feedback.send_notifications", bind=True)
def send_notifications(self: Task) -> None:  # pylint: disable=unused-argument
    """Send the queued emails."""
    if emails_enabled():
        deliver_due(_load_db())


@celery_app.task(name="moh_feedback.daily_digest", bind=True)
def daily_digest(self: Task) -> None:  # pylint: disable=unused-argument
    """Queue each handler's daily summary."""
    if emails_enabled():
        queue_daily_digest(_load_db())


@celery_app.task(name="moh_feedback.auto_close", bind=True)
def auto_close(self: Task) -> None:  # pylint: disable=unused-argument
    """Close items the sender has not responded to."""
    if _automation_enabled():
        auto_close_items(_load_db())


@celery_app.task(name="moh_feedback.escalate", bind=True)
def escalate(self: Task) -> None:  # pylint: disable=unused-argument
    """Pass overdue items to the next level."""
    if _automation_enabled():
        escalate_overdue_items(_load_db())


@celery_app.task(name="moh_feedback.route_pending", bind=True)
def route_pending(self: Task) -> None:  # pylint: disable=unused-argument
    """Route items saved while org units were unavailable."""
    if _automation_enabled():
        route_pending_items(_load_db())
