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
"""Work out the counts on the Area numbers page. It never touches messages."""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping

from superset.moh_feedback.org_units import OrgUnit
from superset.moh_feedback.workflow import (
    CLOSED,
    CONFIRMED,
    DECLINED,
    is_overdue,
    NO_RESPONSE,
)

_LEVELS = range(1, 8)
_SECONDS_PER_HOUR = 3600
_HOURS_PER_DAY = 24
_OFFICE_ROWS = 15
OUTCOMES = ("Confirmed solved", "Closed, no response", "Declined", "Still open")
_CLOSED_OUTCOMES = {
    CONFIRMED: OUTCOMES[0],
    NO_RESPONSE: OUTCOMES[1],
    DECLINED: OUTCOMES[2],
}


@dataclass(frozen=True)
class OfficeNumbers:
    """How much is waiting at one office."""

    name: str
    open_items: int
    overdue: int
    oldest_days: int


@dataclass(frozen=True)
class AreaNumbers:
    """The counts for one area and period."""

    received: int
    median_first_response: str | None
    target_met_percent: int | None
    overdue_now: int
    by_type: list[tuple[str, int]]
    outcomes: list[tuple[str, int]]
    reopened: int
    by_office: list["OfficeNumbers"]


def in_area(item: Any, area_ids: set[str], target_units: Mapping[str, OrgUnit]) -> bool:
    """Return whether an item was sent from, or sent to, a unit in the area."""
    origins = {getattr(item, f"origin_level{level}id") for level in _LEVELS}
    origins.add(item.origin_unit_id)
    if origins & area_ids or item.target_unit_id in area_ids:
        return True
    target = target_units.get(item.target_unit_id)
    return target is not None and bool(set(target.level_ids) & area_ids)


def describe_duration(seconds: float) -> str:
    """Show a length of time in whichever of hours or days reads better."""
    hours = seconds / _SECONDS_PER_HOUR
    if hours < _HOURS_PER_DAY:
        whole = round(hours)
        if whole < 1:
            return "Under 1 hour"
        return f"{whole} hour{'s' if whole != 1 else ''}"
    days = round(hours / _HOURS_PER_DAY, 1)
    return f"{days:g} day{'s' if days != 1 else ''}"


def _median_first_response(items: list[Any]) -> str | None:
    seconds = [
        (item.first_response_on - item.created_on).total_seconds()
        for item in items
        if item.first_response_on is not None
    ]
    return describe_duration(statistics.median(seconds)) if seconds else None


def _target_met_percent(items: list[Any], now: datetime) -> int | None:
    """Return the share on time, of items responded to or already past their date."""
    met = 0
    judged = 0
    for item in items:
        due = item.first_response_due_on
        if due is None:
            continue
        if item.first_response_on is not None:
            judged += 1
            met += item.first_response_on <= due
        elif now > due:
            judged += 1
    return round(100 * met / judged) if judged else None


def _outcome(item: Any) -> str:
    if item.status != CLOSED:
        return OUTCOMES[3]
    return _CLOSED_OUTCOMES.get(item.closure_reason, OUTCOMES[0])


def _by_office(items: list[Any], now: datetime) -> list[OfficeNumbers]:
    """List the offices holding open items, those with the most overdue first."""
    waiting: dict[str, list[Any]] = {}
    for item in items:
        if item.status != CLOSED and item.target_unit_id:
            waiting.setdefault(item.target_unit_name or "Unknown", []).append(item)
    offices = [
        OfficeNumbers(
            name,
            len(held),
            sum(is_overdue(item, now) for item in held),
            max((now - item.created_on).days for item in held),
        )
        for name, held in waiting.items()
    ]
    offices.sort(key=lambda o: (-o.overdue, -o.open_items, o.name))
    return offices[:_OFFICE_ROWS]


def summarise(
    items: Iterable[Any],
    reopened_item_ids: set[int],
    type_labels: Mapping[str, str],
    now: datetime,
) -> AreaNumbers:
    """Count what happened to ``items``."""
    chosen = list(items)
    types = Counter(type_labels.get(item.type, item.type) for item in chosen)
    outcomes = Counter(_outcome(item) for item in chosen)
    return AreaNumbers(
        received=len(chosen),
        median_first_response=_median_first_response(chosen),
        target_met_percent=_target_met_percent(chosen, now),
        overdue_now=sum(is_overdue(item, now) for item in chosen),
        by_type=types.most_common(),
        outcomes=[(name, outcomes[name]) for name in OUTCOMES],
        reopened=sum(item.id in reopened_item_ids for item in chosen),
        by_office=_by_office(chosen, now),
    )
