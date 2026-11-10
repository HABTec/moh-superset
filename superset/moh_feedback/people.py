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
"""Find a named person to add to an item of feedback.

Only exact matches are returned, so the search cannot be used to browse staff.
A search result carries a signed token, so a person can only be added by someone
who found them, and without the browser ever seeing their account details.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable

from flask import current_app
from itsdangerous import BadData, URLSafeTimedSerializer

from superset.moh_feedback.org_units import (
    get_user_units,
    OrgUnitLookupError,
    selectable_units,
)

_TOKEN_SALT = "moh-feedback-person"  # noqa: S105
# Long enough for someone to finish writing their message after searching
_TOKEN_MAX_AGE_SECONDS = 4 * 60 * 60
TERM_MIN_LENGTH = 3
TERM_MAX_LENGTH = 320


@dataclass(frozen=True)
class FoundPerson:
    """A person as shown to whoever searched for them."""

    user_id: int
    name: str
    paths: tuple[str, ...]


def normalise(value: str | None) -> str:
    """Make text comparable, ignoring capitalisation and spacing differences."""
    return " ".join(unicodedata.normalize("NFKC", value or "").split()).casefold()


def matches_exactly(term: str, account: Any) -> bool:
    """Return whether a normalised term is this account's whole email or name."""
    first, last = account.first_name or "", account.last_name or ""
    return term in {
        normalise(account.email),
        normalise(account.username),
        normalise(f"{first} {last}"),
        normalise(f"{last} {first}"),
    }


def is_searchable(term: str) -> bool:
    return TERM_MIN_LENGTH <= len(normalise(term)) <= TERM_MAX_LENGTH


def active_accounts() -> list[Any]:
    """Return every active account.

    Matching is done in Python because databases differ in how they compare
    capitalisation and Unicode, and names can be stored with irregular spacing.
    """
    # pylint: disable=import-outside-toplevel
    from superset.extensions import db, security_manager

    user_model = security_manager.user_model
    return (
        db.session.query(
            user_model.id,
            user_model.username,
            user_model.email,
            user_model.first_name,
            user_model.last_name,
        )
        .filter(user_model.active)
        .all()
    )


def active_user_ids(user_ids: Iterable[int]) -> set[int]:
    """Return which of these accounts are still active."""
    # pylint: disable=import-outside-toplevel
    from superset.extensions import db, security_manager

    wanted = sorted(set(user_ids))
    if not wanted:
        return set()
    user_model = security_manager.user_model
    rows = (
        db.session.query(user_model.id)
        .filter(user_model.active, user_model.id.in_(wanted))
        .all()
    )
    return {row[0] for row in rows}


def _full_name(account: Any) -> str:
    name = f"{account.first_name or ''} {account.last_name or ''}"
    return " ".join(name.split()) or "Name not recorded"


def find_people(term: str, searcher_id: int, limit: int) -> list[FoundPerson]:
    """Return the people exactly matching ``term``, with their org-unit paths.

    Raises ``OrgUnitLookupError`` when a path cannot be read, because the
    searcher must always be able to see which unit a person belongs to.
    """
    wanted = normalise(term)
    matched = [
        account
        for account in active_accounts()
        if account.id != searcher_id and matches_exactly(wanted, account)
    ]
    matched.sort(key=lambda account: (_full_name(account), account.id))
    people = []
    for account in matched[:limit]:
        units = get_user_units(account.username)
        if units is None:
            raise OrgUnitLookupError("org units unavailable")
        paths = tuple(unit.path for unit in selectable_units(units))
        people.append(FoundPerson(account.id, _full_name(account), paths))
    return people


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.secret_key, salt=_TOKEN_SALT)


def person_token(person: FoundPerson, searcher_id: int) -> str:
    """Sign a search result so that only this searcher can add this person."""
    return _serializer().dumps(
        {
            "user_id": person.user_id,
            "by": searcher_id,
            "name": person.name,
            "paths": list(person.paths),
        }
    )


def read_person_token(token: str, searcher_id: int) -> FoundPerson | None:
    """Return the person in a token, or None if it is not this searcher's."""
    try:
        data = _serializer().loads(token, max_age=_TOKEN_MAX_AGE_SECONDS)
    except BadData:
        return None
    if data["by"] != searcher_id:
        return None
    return FoundPerson(data["user_id"], data["name"], tuple(data["paths"]))
