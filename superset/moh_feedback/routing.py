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
"""Find which unit receives feedback, up or down the org-unit tree.

A unit can only receive feedback if it is open and has an active user who can
handle it, because most org units have no portal user at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from flask import current_app

from superset.moh_feedback.org_units import (
    get_top_units,
    get_units,
    get_usernames_by_unit,
    OrgUnit,
    search_units_below,
)
from superset.moh_feedback.workflow import Person

DEFAULT_HANDLER_ROLES = ("OrgUnitViewer",)
_QUERY_BATCH_SIZE = 1000


@dataclass(frozen=True)
class UnitOption:
    """A unit that can be chosen when sending feedback down."""

    unit: OrgUnit
    active_users: int
    destination: OrgUnit | None


def _active_handlers(usernames: Iterable[str]) -> set[str]:
    """Return which usernames are active portal users allowed to handle items."""
    # pylint: disable=import-outside-toplevel
    from superset.extensions import db, security_manager

    names = sorted(set(usernames))
    roles = current_app.config.get("MOH_FEEDBACK_HANDLER_ROLES", DEFAULT_HANDLER_ROLES)
    user_model = security_manager.user_model
    role_model = security_manager.role_model
    handlers: set[str] = set()
    for start in range(0, len(names), _QUERY_BATCH_SIZE):
        rows = (
            db.session.query(user_model.username)
            .join(user_model.roles)
            .filter(
                user_model.active,
                user_model.username.in_(names[start : start + _QUERY_BATCH_SIZE]),
                role_model.name.in_(list(roles)),
            )
            .all()
        )
        handlers.update(row[0] for row in rows)
    return handlers


def count_handlers(unit_ids: Iterable[str], sender: str) -> dict[str, int]:
    """Count each unit's active handlers, not counting the sender."""
    usernames_by_unit = get_usernames_by_unit(unit_ids)
    handlers = _active_handlers(
        name for names in usernames_by_unit.values() for name in names
    )
    handlers = {name for name in handlers if name.lower() != sender.lower()}
    return {
        unit_id: len(names & handlers) for unit_id, names in usernames_by_unit.items()
    }


def unit_handlers(unit_id: str, excluded_user_id: int | None) -> list[Person]:
    """Return the active handlers at a unit, for assigning an item to one."""
    # pylint: disable=import-outside-toplevel
    from superset.extensions import db, security_manager

    usernames = sorted(get_usernames_by_unit([unit_id]).get(unit_id, set()))
    if not usernames:
        return []
    roles = current_app.config.get("MOH_FEEDBACK_HANDLER_ROLES", DEFAULT_HANDLER_ROLES)
    user_model = security_manager.user_model
    people = {
        user.id: Person(user.id, f"{user.first_name} {user.last_name}".strip())
        for user in db.session.query(user_model)
        .join(user_model.roles)
        .filter(
            user_model.active,
            user_model.username.in_(usernames[:_QUERY_BATCH_SIZE]),
            security_manager.role_model.name.in_(list(roles)),
        )
        .all()
        if user.id != excluded_user_id
    }
    return sorted(people.values(), key=lambda person: person.name)


def _first_able_to_receive(
    chain: Iterable[str], units: dict[str, OrgUnit], handlers: dict[str, int]
) -> OrgUnit | None:
    """Return the first unit in ``chain`` that is open and has a handler."""
    for unit_id in chain:
        unit = units.get(unit_id)
        if unit is not None and not unit.closed and handlers.get(unit_id, 0) > 0:
            return unit
    return None


def find_destination_up(origin: OrgUnit | None, sender: str) -> OrgUnit | None:
    """Return the unit that receives feedback sent upward from ``origin``.

    Top-level users have nobody above them, so their colleagues receive it.
    Senders without an org unit go to the top level.
    """
    if origin is None:
        top_units = {unit.id: unit for unit in get_top_units()}
        return _first_able_to_receive(
            sorted(top_units), top_units, count_handlers(top_units, sender)
        )
    chain = origin.ancestor_ids or (origin.id,)
    units = {origin.id: origin, **get_units(chain)}
    return _first_able_to_receive(chain, units, count_handlers(chain, sender))


def find_escalation_target(
    current: OrgUnit, sender: str, direction: str, origin_unit_id: str | None
) -> OrgUnit | None:
    """Return the next unit able to take an overdue item, if there is one.

    Feedback sent down climbs towards its sender and stops one level below them.
    """
    chain = current.ancestor_ids
    if direction == "down" and origin_unit_id in chain:
        chain = chain[: chain.index(origin_unit_id)]
    units = get_units(chain)
    return _first_able_to_receive(chain, units, count_handlers(chain, sender))


def is_below(origin: OrgUnit, target: OrgUnit) -> bool:
    """Return whether ``target`` is somewhere below ``origin`` in the tree."""
    return origin.id in target.ancestor_ids


def _downward_chain(origin: OrgUnit, target: OrgUnit) -> tuple[str, ...]:
    """The target, then the units above it, stopping before ``origin``."""
    ancestors = target.ancestor_ids
    return (target.id, *ancestors[: ancestors.index(origin.id)])


def find_destination_down(
    origin: OrgUnit, target: OrgUnit, sender: str
) -> OrgUnit | None:
    """Return the unit that receives feedback sent down to ``target``.

    If the target has no active handler, the nearest unit above it and below
    the sender receives it instead.
    """
    chain = _downward_chain(origin, target)
    units = {target.id: target, **get_units(chain)}
    return _first_able_to_receive(chain, units, count_handlers(chain, sender))


def describe_units_below(
    origin: OrgUnit, term: str, sender: str, limit: int
) -> list[UnitOption]:
    """Search units below ``origin``, showing who would receive feedback for each."""
    targets = search_units_below(origin, term, limit)
    chains = {target.id: _downward_chain(origin, target) for target in targets}
    all_ids: set[Any] = {unit_id for chain in chains.values() for unit_id in chain}
    units = get_units(all_ids)
    handlers = count_handlers(all_ids, sender)
    return [
        UnitOption(
            unit=target,
            active_users=handlers.get(target.id, 0),
            destination=_first_able_to_receive(chains[target.id], units, handlers),
        )
        for target in targets
    ]
