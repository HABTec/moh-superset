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
"""Work out when an item of feedback needs a response and an answer.

Deadlines count Monday to Friday. A deadline is the end of its day in Addis
Ababa, so an item is not overdue until the date shown has passed.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from flask import current_app

LOCAL_TIMEZONE = ZoneInfo("Africa/Addis_Ababa")
HIGH = "high"
NORMAL = "normal"
LOW = "low"
PRIORITIES = (HIGH, NORMAL, LOW)
# Working days for the first response, and to finish; None means no deadline
DEFAULT_DEADLINES: dict[str, tuple[int | None, int | None]] = {
    HIGH: (2, 5),
    NORMAL: (5, 14),
    LOW: (5, None),
}
_SATURDAY = 5


def local_date(value: datetime) -> date:
    """Return the Addis Ababa date of a stored UTC time."""
    return value.replace(tzinfo=timezone.utc).astimezone(LOCAL_TIMEZONE).date()


def _end_of_day(day: date) -> datetime:
    local = datetime.combine(day, time(23, 59, 59), LOCAL_TIMEZONE)
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def _is_working_day(day: date) -> bool:
    return day.weekday() < _SATURDAY


def add_working_days(start: datetime, days: int) -> datetime:
    """Return the end of the day that is ``days`` working days after ``start``."""
    day = local_date(start)
    remaining = days
    while remaining > 0:
        day += timedelta(days=1)
        if _is_working_day(day):
            remaining -= 1
    return _end_of_day(day)


def working_days_between(start: datetime, end: datetime) -> int:
    """Count the working days after the date of ``start`` up to that of ``end``."""
    day = local_date(start)
    last = local_date(end)
    count = 0
    while day < last:
        day += timedelta(days=1)
        count += _is_working_day(day)
    return count


def _deadline(start: datetime, days: int | None, paused_days: int) -> datetime | None:
    return None if days is None else add_working_days(start, days + paused_days)


def refresh_deadlines(item: Any) -> None:
    """Set an item's deadlines from its priority, clock start and paused days."""
    rules = current_app.config.get("MOH_FEEDBACK_DEADLINES", DEFAULT_DEADLINES)
    first_response_days, due_days = rules[item.priority]
    start = item.clock_started_on or item.created_on
    paused_days = item.paused_days or 0
    item.first_response_due_on = _deadline(start, first_response_days, paused_days)
    item.due_on = _deadline(start, due_days, paused_days)
