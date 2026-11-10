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
"""The rules for what can happen to an item of feedback, and in which status."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, NamedTuple

from sqlalchemy import and_, or_

from superset.moh_feedback.deadlines import refresh_deadlines, working_days_between

NEW = "new"
IN_REVIEW = "in_review"
ASSIGNED = "assigned"
NEEDS_INFO = "needs_info"
ANSWERED = "answered"
CLOSED = "closed"
DECLINED = "declined"
CONFIRMED = "confirmed"
NO_RESPONSE = "no_response"

START_REVIEW = "start_review"
ASSIGN = "assign"
ASK = "ask"
ANSWER = "answer"
REPLY = "reply"
DECLINE = "decline"
NOTE = "note"
SET_PRIORITY = "set_priority"
SENDER_REPLY = "sender_reply"

_BEING_HANDLED = (NEW, IN_REVIEW, ASSIGNED)
# The first of these actions is the response counted against the deadline
_FIRST_RESPONSE_ACTIONS = (ASSIGN, ASK, ANSWER, REPLY)
# After these the item waits on the sender, so the handler's clock stops
_PAUSING_ACTIONS = (ASK, ANSWER)


class Person(NamedTuple):
    id: int | None
    name: str


@dataclass(frozen=True)
class Action:
    """One thing that can be done to an item."""

    event_type: str
    from_statuses: tuple[str, ...]
    # None leaves the status as it is
    to_status: str | None
    needs_message: bool = False
    internal: bool = False


ACTIONS = {
    START_REVIEW: Action("review_started", (NEW,), IN_REVIEW),
    ASSIGN: Action("assigned", _BEING_HANDLED, ASSIGNED),
    ASK: Action("asked", _BEING_HANDLED, NEEDS_INFO, needs_message=True),
    ANSWER: Action("answered", _BEING_HANDLED, ANSWERED, needs_message=True),
    REPLY: Action(
        "replied", (*_BEING_HANDLED, NEEDS_INFO, ANSWERED), None, needs_message=True
    ),
    DECLINE: Action("declined", _BEING_HANDLED, CLOSED, needs_message=True),
    NOTE: Action(
        "internal_note",
        (*_BEING_HANDLED, NEEDS_INFO, ANSWERED),
        None,
        needs_message=True,
        internal=True,
    ),
    SET_PRIORITY: Action("priority_changed", (*_BEING_HANDLED, NEEDS_INFO), None),
}
MOVE_ACTION = Action("moved", (*_BEING_HANDLED, NEEDS_INFO), NEW, True)
SENDER_REPLY_ACTION = Action("sender_reply", (NEEDS_INFO,), IN_REVIEW, True)
PARTICIPANT_COMMENT_ACTION = Action(
    "participant_comment", (*_BEING_HANDLED, NEEDS_INFO, ANSWERED), None, True
)
SENDER_MESSAGE_ACTION = Action("sender_message", _BEING_HANDLED, None, True)
REOPEN_ACTION = Action("reopened", (CLOSED,), IN_REVIEW, True)
AUTO_CLOSE_ACTION = Action("auto_closed", (ANSWERED, NEEDS_INFO), CLOSED)
SENDER_SOLVED_ACTION = Action("sender_solved", (ANSWERED,), CLOSED)
SENDER_NOT_SOLVED_ACTION = Action("sender_not_solved", (ANSWERED,), IN_REVIEW, True)


def allowed_actions(status: str) -> set[str]:
    """Return the handler actions available for an item in ``status``."""
    return {name for name, action in ACTIONS.items() if status in action.from_statuses}


def _assign(item: Any, person: Person) -> None:
    item.assigned_to_fk = person.id
    item.assignee_name = person.name[:255]


def _record(
    item: Any,
    action: Action,
    actor: Person,
    event_model: Any,
    message: str | None,
) -> None:
    previous = item.status
    if action.to_status:
        item.status = action.to_status
    item.events.append(
        event_model(
            event_type=action.event_type,
            from_status=previous,
            to_status=item.status,
            user_id=actor.id,
            actor_name=actor.name[:255],
            message=message,
            is_internal=action.internal,
        )
    )


def apply_action(
    item: Any,
    name: str,
    actor: Person,
    event_model: Any,
    now: datetime,
    message: str | None = None,
    assignee: Person | None = None,
    priority: str | None = None,
) -> None:
    """Apply a handler's action, which the caller has checked is allowed."""
    if name in _PAUSING_ACTIONS:
        item.paused_on = now
    if name == SET_PRIORITY and priority is not None:
        item.priority = priority
        message = priority.capitalize()
        refresh_deadlines(item)
    if name == ASSIGN and assignee is not None:
        _assign(item, assignee)
        message = assignee.name
    if name == ANSWER:
        if item.assigned_to_fk is None:
            _assign(item, actor)
        item.answered_on = now
    if name == DECLINE:
        item.closed_on = now
        item.closure_reason = DECLINED
    if name in _FIRST_RESPONSE_ACTIONS and item.first_response_on is None:
        item.first_response_on = now
    _record(item, ACTIONS[name], actor, event_model, message)


def _resume_clock(item: Any, now: datetime) -> None:
    """Restart a paused clock, moving the deadlines back by the days it was paused."""
    if item.paused_on is None:
        return
    item.paused_days = (item.paused_days or 0) + working_days_between(
        item.paused_on, now
    )
    item.paused_on = None
    refresh_deadlines(item)


def is_overdue(item: Any, now: datetime) -> bool:
    """Return whether a unit is late with an item it is still handling."""
    if item.status not in _BEING_HANDLED:
        return False
    if (
        item.first_response_on is None
        and item.first_response_due_on is not None
        and now > item.first_response_due_on
    ):
        return True
    return item.due_on is not None and now > item.due_on


def overdue_condition(feedback_model: Any, now: datetime) -> Any:
    """Return the database filter matching what ``is_overdue`` decides."""
    return and_(
        feedback_model.status.in_(_BEING_HANDLED),
        or_(
            feedback_model.due_on < now,
            and_(
                feedback_model.first_response_on.is_(None),
                feedback_model.first_response_due_on < now,
            ),
        ),
    )


def apply_sender_message(
    item: Any, actor: Person, event_model: Any, message: str
) -> None:
    """Record more information from the sender, leaving the status as it is."""
    _record(item, SENDER_MESSAGE_ACTION, actor, event_model, message)


def apply_reopen(
    item: Any, actor: Person, event_model: Any, now: datetime, reason: str
) -> None:
    """Give a closed item back to its handlers, with fresh deadlines."""
    item.closed_on = None
    item.closure_reason = None
    item.answered_on = None
    item.paused_on = None
    item.paused_days = 0
    item.clock_started_on = now
    refresh_deadlines(item)
    _record(item, REOPEN_ACTION, actor, event_model, reason)


def apply_move(
    item: Any, actor: Person, event_model: Any, now: datetime, reason: str
) -> None:
    """Start the item afresh for the unit it is being passed to."""
    item.assigned_to_fk = None
    item.assignee_name = None
    item.first_response_on = None
    item.answered_on = None
    item.paused_on = None
    item.paused_days = 0
    item.clock_started_on = now
    refresh_deadlines(item)
    _record(item, MOVE_ACTION, actor, event_model, reason)


def apply_auto_close(item: Any, actor: Person, event_model: Any, now: datetime) -> None:
    """Close an item that has waited on its sender for too long."""
    item.closed_on = now
    item.closure_reason = NO_RESPONSE
    item.paused_on = None
    _record(item, AUTO_CLOSE_ACTION, actor, event_model, None)


def apply_sender_reply(
    item: Any, actor: Person, event_model: Any, message: str, now: datetime
) -> None:
    """Record the sender's reply, returning the item to its handlers."""
    _resume_clock(item, now)
    _record(item, SENDER_REPLY_ACTION, actor, event_model, message)


def apply_participant_comment(
    item: Any, actor: Person, event_model: Any, message: str
) -> None:
    """Record a comment from a person added to the item."""
    _record(item, PARTICIPANT_COMMENT_ACTION, actor, event_model, message)


def apply_sender_decision(
    item: Any,
    solved: bool,
    actor: Person,
    event_model: Any,
    now: datetime,
    message: str | None = None,
) -> None:
    """Close an answered item, or return it to its handlers if it is not solved."""
    if solved:
        item.closed_on = now
        item.closure_reason = CONFIRMED
    else:
        item.answered_on = None
        _resume_clock(item, now)
    action = SENDER_SOLVED_ACTION if solved else SENDER_NOT_SOLVED_ACTION
    _record(item, action, actor, event_model, message)
