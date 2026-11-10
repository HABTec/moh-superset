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
"""Make another unit responsible for an item of feedback."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from superset.moh_feedback.notifications import notify_moved
from superset.moh_feedback.org_units import OrgUnit
from superset.moh_feedback.workflow import apply_move, Person


def responsible_unit_id(item: Any) -> str | None:
    return next((row.unit_id for row in item.unit_access if row.is_current), None)


def sender_username(item: Any, db: Any) -> str:
    """Return the username of an item's sender, or nothing if the account is gone."""
    from superset.extensions import (  # pylint: disable=import-outside-toplevel
        security_manager,
    )

    if item.created_by_fk is None:
        return ""
    user_model = security_manager.user_model
    row = (
        db.session.query(user_model.username)
        .filter_by(id=item.created_by_fk)
        .one_or_none()
    )
    return row[0] if row else ""


def hand_over(  # pylint: disable=too-many-arguments
    db: Any,
    models: tuple[Any, Any],
    item: Any,
    destination: OrgUnit,
    actor: Person,
    reason: str,
    now: datetime,
    access_reason: str = "moved",
) -> None:
    """Make ``destination`` responsible; the previous unit keeps read access."""
    event_model, access_model = models
    previous_unit_id = responsible_unit_id(item)
    previous_assignee = item.assigned_to_fk
    for row in item.unit_access:
        row.is_current = False
    # Only one row per item can be current, so this must be saved before the new one
    db.session.flush()
    apply_move(item, actor, event_model, now, reason)
    item.events[-1].from_unit_id = previous_unit_id
    item.events[-1].to_unit_id = destination.id
    item.target_unit_id = destination.id
    item.target_unit_name = destination.name[:255]
    item.target_path = destination.path
    item.unit_access.append(
        access_model(
            unit_id=destination.id,
            unit_name=destination.name[:255],
            reason=access_reason,
            is_current=True,
        )
    )
    item.events.append(
        event_model(
            event_type="routed", to_unit_id=destination.id, message=destination.name
        )
    )
    notify_moved(item, previous_assignee, destination.id, actor)
