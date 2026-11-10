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
"""Signed-in users can send feedback, saved with their account and org unit."""

from __future__ import annotations

import contextlib
import io
import smtplib
import stat as file_stat
import time
import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest
from flask import Flask
from flask.testing import FlaskClient
from PIL import Image, PngImagePlugin
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from superset.moh_feedback import (
    attachments,
    deadlines,
    notifications,
    org_units,
    people,
    routing,
    stats,
    tasks,
    views,
)
from superset.moh_feedback.org_units import (
    org_unit_from_row,
    OrgUnit,
    OrgUnitLookupError,
    unit_ids_for_username,
)
from superset.moh_feedback.workflow import allowed_actions, is_overdue, Person
from superset.utils import json

UNIT = OrgUnit(
    id="unit-1",
    name="Sample Woreda",
    path="Federal › Sample Region › Sample Woreda",
    level_ids=("root", "region", "unit-1", None, None, None, None),
    closed=False,
)
OTHER_UNIT = OrgUnit(
    "unit-2", "Other", "Federal › Other", ("root",) + (None,) * 6, False
)
CLOSED_UNIT = OrgUnit(
    "unit-3", "Closed", "Federal › Closed", ("root",) + (None,) * 6, True
)
PARENT_UNIT = OrgUnit(
    "region",
    "Sample Region",
    "Federal › Sample Region",
    ("root", "region", None, None, None, None, None),
    False,
    level=2,
)
MESSAGE = "The ANC figure for this facility looks too high."


def _search_model() -> Any:
    from superset.models.moh_feedback import MohFeedbackPersonSearch

    return MohFeedbackPersonSearch


HANDLING_ACTIONS = {
    "assign",
    "ask",
    "answer",
    "reply",
    "decline",
    "note",
    "set_priority",
}


@pytest.fixture
def models(session: Session) -> tuple[Any, Any]:
    from flask_appbuilder.security.sqla.models import User

    from superset.models.moh_feedback import (
        MohFeedback,
        MohFeedbackAttachment,
        MohFeedbackEvent,
        MohFeedbackNotification,
        MohFeedbackParticipant,
        MohFeedbackPersonSearch,
        MohFeedbackUnitAccess,
    )

    MohFeedback.metadata.create_all(
        session.get_bind(),
        tables=[
            User.__table__,
            MohFeedback.__table__,
            MohFeedbackEvent.__table__,
            MohFeedbackUnitAccess.__table__,
            MohFeedbackParticipant.__table__,
            MohFeedbackPersonSearch.__table__,
            MohFeedbackNotification.__table__,
            MohFeedbackAttachment.__table__,
        ],
    )
    return MohFeedback, MohFeedbackEvent


@pytest.fixture
def user() -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        username="sample.user",
        first_name="Sample",
        last_name="User",
        email="sample.user@example.org",
        roles=[SimpleNamespace(name="OrgUnitViewer")],
        is_authenticated=True,
    )


@pytest.fixture
def units() -> list[OrgUnit]:
    return [UNIT]


@pytest.fixture
def client(
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
    units: list[OrgUnit],
) -> Iterator[FlaskClient]:
    app = Flask(__name__)
    app.secret_key = "test-key"  # noqa: S105
    app.config["MOH_FEEDBACK_ENABLED"] = True
    app.register_blueprint(views.moh_feedback_bp)
    with (
        mock.patch.object(views, "current_user", user),
        mock.patch.object(views, "get_user_units", side_effect=lambda _: list(units)),
        mock.patch.object(
            views, "_load_db", return_value=SimpleNamespace(session=session)
        ),
        mock.patch.object(views, "_load_models", return_value=models),
        mock.patch.object(
            views,
            "_load_access_model",
            side_effect=lambda: models[0].unit_access.property.mapper.class_,
        ),
        mock.patch.object(
            views,
            "_load_participant_model",
            side_effect=lambda: models[0].participants.property.mapper.class_,
        ),
        mock.patch.object(
            views,
            "_load_attachment_model",
            side_effect=lambda: models[0].attachments.property.mapper.class_,
        ),
        mock.patch.object(
            views,
            "_load_search_model",
            side_effect=lambda: _search_model(),
        ),
        mock.patch.object(views, "find_destination_up", return_value=PARENT_UNIT),
        mock.patch.object(views, "_page_title", return_value=None),
    ):
        yield app.test_client()


def form_fields(client: FlaskClient, url: str = "/moh/feedback/new") -> dict[str, str]:
    html = client.get(url).get_data(as_text=True)
    return {
        name: _hidden_value(html, name)
        for name in ("csrf_token", "submission_id", "page_url")
    }


def _hidden_value(html: str, name: str) -> str:
    marker = f'name="{name}" value="'
    start = html.index(marker) + len(marker)
    return html[start : html.index('"', start)]


def submit(client: FlaskClient, fields: dict[str, str], **overrides: str) -> Any:
    data = {**fields, "type": "wrong_data", "message": MESSAGE, **overrides}
    return client.post("/moh/feedback/", data=data)


def test_saves_feedback_with_account_org_unit_and_history(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    fields = form_fields(client, "/moh/feedback/new?from=/superset/dashboard/5/")

    response = submit(client, fields)

    assert response.status_code == 302
    saved = session.query(models[0]).one()
    assert saved.created_by_fk == 7
    assert saved.sender_name == "Sample User"
    assert saved.sender_email == "sample.user@example.org"
    assert saved.sender_role == "OrgUnitViewer"
    assert saved.origin_unit_id == "unit-1"
    assert saved.origin_path == UNIT.path
    assert saved.origin_level3id == "unit-1"
    assert saved.origin_level4id is None
    assert saved.type == "wrong_data"
    assert saved.message == MESSAGE
    assert saved.page_url == "/superset/dashboard/5/"
    assert saved.status == "new"
    assert saved.uuid is not None
    event = session.query(models[1]).filter_by(event_type="created").one()
    assert (event.feedback_id, event.event_type) == (saved.id, "created")
    assert (event.to_status, event.user_id) == ("new", 7)
    assert saved.reference in client.get("/moh/feedback/new").get_data(as_text=True)


def test_browser_cannot_override_the_sender(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    submit(
        client,
        form_fields(client),
        created_by_fk="99",
        sender_name="Someone Else",
        origin_unit_id="unit-9",
    )

    saved = session.query(models[0]).one()
    assert (saved.created_by_fk, saved.sender_name) == (7, "Sample User")
    assert saved.origin_unit_id == "unit-1"


def test_repeated_submit_saves_one_item(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    fields = form_fields(client)

    assert submit(client, fields).status_code == 302
    assert submit(client, fields).status_code == 302

    assert session.query(models[0]).count() == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"type": "not-a-type"},
        {"message": "too short"},
        {"message": "x" * 2001},
        {"csrf_token": "forged"},
        {"submission_id": "not-valid"},
    ],
)
def test_invalid_submissions_are_not_saved_and_keep_the_message(
    client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    overrides: dict[str, str],
) -> None:
    response = submit(client, form_fields(client), **overrides)

    assert response.status_code == 400
    assert session.query(models[0]).count() == 0
    if "message" not in overrides:
        assert MESSAGE in response.get_data(as_text=True)


def test_message_is_displayed_as_plain_text(client: FlaskClient) -> None:
    script = "<script>alert('x')</script> long enough"

    html = submit(client, form_fields(client), type="bad", message=script).get_data(
        as_text=True
    )

    assert script not in html
    assert "&lt;script&gt;" in html


def test_hourly_limit(
    client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
) -> None:
    client.application.config["MOH_FEEDBACK_MAX_PER_HOUR"] = 1
    assert submit(client, form_fields(client)).status_code == 302

    assert submit(client, form_fields(client)).status_code == 429

    saved = session.query(models[0]).one()
    saved.created_on -= timedelta(hours=2)
    session.flush()
    assert submit(client, form_fields(client)).status_code == 302


@pytest.mark.parametrize("units", [[]])
def test_saves_without_org_unit_when_none_is_available(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    assert "Not available" in client.get("/moh/feedback/new").get_data(as_text=True)

    assert submit(client, form_fields(client)).status_code == 302

    saved = session.query(models[0]).one()
    assert saved.origin_unit_id is None
    assert saved.origin_level1id is None


@pytest.mark.parametrize("units", [[UNIT, OTHER_UNIT]])
def test_user_with_several_units_must_choose_one_of_their_own(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    assert submit(client, form_fields(client)).status_code == 400
    assert submit(client, form_fields(client), unit_id="not-mine").status_code == 400
    assert session.query(models[0]).count() == 0

    assert submit(client, form_fields(client), unit_id="unit-2").status_code == 302

    assert session.query(models[0]).one().origin_unit_id == "unit-2"


@pytest.mark.parametrize("units", [[UNIT, CLOSED_UNIT]])
def test_open_unit_is_used_when_the_user_also_has_a_closed_one(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    assert submit(client, form_fields(client)).status_code == 302

    assert session.query(models[0]).one().origin_unit_id == "unit-1"


@pytest.mark.parametrize("units", [[CLOSED_UNIT]])
def test_closed_unit_is_recorded_when_it_is_the_only_one(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    assert submit(client, form_fields(client)).status_code == 302

    assert session.query(models[0]).one().origin_unit_id == "unit-3"


def test_pages_are_hidden_while_the_feature_is_off(client: FlaskClient) -> None:
    client.application.config["MOH_FEEDBACK_ENABLED"] = False

    assert client.get("/moh/feedback/new").status_code == 404
    assert client.post("/moh/feedback/").status_code == 404


def test_signed_out_user_is_sent_to_login(
    client: FlaskClient, user: SimpleNamespace
) -> None:
    user.is_authenticated = False

    response = client.get("/moh/feedback/new?from=/superset/dashboard/5/")

    assert response.status_code == 302
    assert response.location == (
        "/login/?next=/moh/feedback/new?from=/superset/dashboard/5/"
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("/superset/dashboard/5/?a=1", "/superset/dashboard/5/?a=1"),
        ("https://evil.example/x", None),
        ("//evil.example/x", None),
        ("/\\evil.example", None),
        ("javascript:alert(1)", None),
        ("/ok\nSet-Cookie: x", None),
        ("/" + "a" * 2048, None),
        ("", None),
        (None, None),
    ],
)
def test_safe_page_url(raw: str | None, expected: str | None) -> None:
    assert views.safe_page_url(raw) == expected


def test_org_unit_from_row_builds_the_path_and_treats_empty_as_missing() -> None:
    row = {
        "id": 42,
        "name": "Sample Woreda",
        "is_closed": 0,
        "level1id": "a",
        "l1name": "Federal",
        "level2id": "b",
        "l2name": "Sample Region",
        "level3id": "",
        "l3name": "",
    }

    unit = org_unit_from_row(row)

    assert unit.id == "42"
    assert unit.path == "Federal › Sample Region"
    assert unit.level_ids[:3] == ("a", "b", None)
    assert unit.closed is False
    assert org_unit_from_row({**row, "is_closed": 1}).closed is True


def test_exact_username_wins_over_a_different_capitalisation() -> None:
    rows = [
        {"username": "Sample.User", "unit_id": "other-unit"},
        {"username": "sample.user", "unit_id": "own-unit"},
    ]

    assert unit_ids_for_username(rows, "sample.user") == ["own-unit"]


def test_other_capitalisation_is_used_when_there_is_no_exact_username() -> None:
    rows = [{"username": "Sample.User", "unit_id": "own-unit"}]

    assert unit_ids_for_username(rows, "sample.user") == ["own-unit"]
    assert unit_ids_for_username([], "sample.user") == []


def add_item(
    session: Session, models: tuple[Any, Any], owner: int | None, message: str = MESSAGE
) -> Any:
    item = models[0](
        submission_id=uuid.uuid4().hex,
        created_by_fk=owner,
        sender_name="Sample User",
        type="question",
        message=message,
        origin_path="Federal › Sample Woreda",
    )
    item.events.append(models[1](event_type="created", to_status="new", user_id=owner))
    session.add(item)
    session.flush()
    return item


def test_my_feedback_lists_only_the_users_items(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    add_item(session, models, 7, "My own feedback message")
    add_item(session, models, 8, "Another user's feedback message")

    html = client.get("/moh/feedback/mine").get_data(as_text=True)

    assert "My own feedback message" in html
    assert "Another user" not in html


def test_my_feedback_shows_newest_first(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    older = add_item(session, models, 7, "The older feedback item")
    older.created_on -= timedelta(days=1)
    add_item(session, models, 7, "The newer feedback item")
    session.flush()

    html = client.get("/moh/feedback/mine").get_data(as_text=True)

    assert html.index("The newer feedback item") < html.index("The older feedback item")


def test_my_feedback_empty_state(client: FlaskClient) -> None:
    html = client.get("/moh/feedback/mine").get_data(as_text=True)

    assert "You have not sent any feedback yet." in html


def test_my_feedback_pages(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    for number in range(26):
        add_item(session, models, 7, f"Feedback item number {number:02d}")

    first = client.get("/moh/feedback/mine").get_data(as_text=True)
    second = client.get("/moh/feedback/mine?page=2").get_data(as_text=True)
    beyond = client.get("/moh/feedback/mine?page=99").get_data(as_text=True)
    invalid = client.get("/moh/feedback/mine?page=x").status_code

    assert "Page 1 of 2" in first
    assert first.count('data-label="Reference"') == 25
    assert second.count('data-label="Reference"') == 1
    assert "Page 2 of 2" in beyond
    assert invalid == 200


def test_sender_sees_their_item_and_its_history(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = add_item(session, models, 7)

    response = client.get(f"/moh/feedback/{item.uuid}")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert item.reference in html
    assert MESSAGE in html
    assert "Federal › Sample Woreda" in html
    assert "Feedback sent" in html


def test_other_users_item_does_not_exist_for_them(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = add_item(session, models, 8)

    assert client.get(f"/moh/feedback/{item.uuid}").status_code == 404


def test_unknown_and_malformed_items_are_not_found(client: FlaskClient) -> None:
    assert client.get(f"/moh/feedback/{uuid.uuid4()}").status_code == 404
    assert client.get("/moh/feedback/not-a-uuid").status_code == 404


def test_stored_text_is_shown_as_plain_text(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    script = "<script>alert('x')</script> saved feedback"
    item = add_item(session, models, 7, script)

    listing = client.get("/moh/feedback/mine").get_data(as_text=True)
    detail = client.get(f"/moh/feedback/{item.uuid}").get_data(as_text=True)

    assert "<script>alert" not in listing
    assert "<script>alert" not in detail
    assert "&lt;script&gt;alert" in detail


def test_my_feedback_pages_follow_the_feature_setting_and_login(
    client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = add_item(session, models, 7)
    url = f"/moh/feedback/{item.uuid}"

    user.is_authenticated = False
    assert client.get("/moh/feedback/mine").status_code == 302
    assert client.get(url).location == f"/login/?next={url}"

    client.application.config["MOH_FEEDBACK_ENABLED"] = False
    assert client.get("/moh/feedback/mine").status_code == 404
    assert client.get(url).status_code == 404


def test_times_are_shown_in_addis_ababa_time() -> None:
    assert views.format_time(datetime(2026, 11, 9, 7, 21)) == "9 Nov 2026, 10:21"


def test_null_character_is_removed_because_postgres_cannot_store_it(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    submit(client, form_fields(client), message="A valid\x00 feedback message")

    assert session.query(models[0]).one().message == "A valid feedback message"


def test_browser_line_breaks_count_as_one_character(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    message = "x" * 1998 + "\r\n" + "y"

    assert submit(client, form_fields(client), message=message).status_code == 302

    assert session.query(models[0]).one().message == "x" * 1998 + "\n" + "y"


def test_message_that_is_only_spaces_is_refused(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    response = submit(client, form_fields(client), message=" " * 50)

    assert response.status_code == 400
    assert session.query(models[0]).count() == 0


def test_amharic_message_is_saved_and_displayed(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    message = "የዚህ ጤና ተቋም መረጃ ትክክል አይደለም።"

    submit(client, form_fields(client), message=message)

    saved = session.query(models[0]).one()
    assert saved.message == message
    assert message in client.get(f"/moh/feedback/{saved.uuid}").get_data(as_text=True)


def test_account_without_name_email_or_roles_can_send(
    client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    user.first_name = None
    user.last_name = ""
    user.email = None
    user.roles = []

    assert submit(client, form_fields(client)).status_code == 302

    saved = session.query(models[0]).one()
    assert saved.sender_name == "sample.user"
    assert saved.sender_email is None
    assert saved.sender_role == ""


def test_same_submission_saved_at_the_same_moment_is_treated_as_sent(
    client: FlaskClient,
) -> None:
    fields = form_fields(client)
    error = IntegrityError("insert", {}, Exception("duplicate"))
    with (
        mock.patch.object(
            views,
            "_find_submission",
            side_effect=[
                None,
                SimpleNamespace(
                    reference="FB-9", target_unit_id=None, first_response_due_on=None
                ),
            ],
        ),
        mock.patch.object(views, "_save_feedback", side_effect=error),
    ):
        response = submit(client, fields)

    assert response.status_code == 302
    assert "FB-9" in client.get("/moh/feedback/new").get_data(as_text=True)


def test_org_unit_lookup_failure_returns_no_units() -> None:
    app = Flask(__name__)
    with (
        app.app_context(),
        mock.patch.object(
            org_units, "_organisation_database", side_effect=OSError("down")
        ),
    ):
        assert org_units.get_user_units("sample.user") is None


def test_org_unit_without_level_names_uses_its_own_name_as_the_path() -> None:
    unit = org_unit_from_row({"id": "1", "name": "Sample Unit", "is_closed": 0})

    assert unit.path == "Sample Unit"


def test_unusual_page_numbers_show_a_valid_page(client: FlaskClient) -> None:
    for page in ("-5", "0", "99999999999999999999", "1.5"):
        assert client.get(f"/moh/feedback/mine?page={page}").status_code == 200


class FakeOrganisationDatabase:
    """Stands in for ClickHouse, optionally taking ``delay`` seconds to answer."""

    def __init__(self, delay: float = 0) -> None:
        self.delay = delay
        self.results = [
            [{"username": "sample.user", "unit_id": "unit-1"}],
            [{"id": "unit-1", "name": "Sample", "l1name": "Federal", "is_closed": 0}],
        ]

    @contextlib.contextmanager
    def get_sqla_engine(self) -> Iterator[Any]:
        yield self

    @contextlib.contextmanager
    def connect(self) -> Iterator[Any]:
        yield self

    def execute(self, *_: Any) -> Any:
        time.sleep(self.delay)
        rows = self.results.pop(0)
        return SimpleNamespace(mappings=lambda: rows)


def lookup_units(
    database: FakeOrganisationDatabase, limit: float
) -> list[OrgUnit] | None:
    app = Flask(__name__)
    app.config["MOH_FEEDBACK_ORG_LOOKUP_TIMEOUT"] = limit
    with (
        app.app_context(),
        mock.patch.object(org_units, "_organisation_database", return_value=database),
    ):
        return org_units.get_user_units("sample.user")


def test_org_unit_lookup_returns_the_units_read_from_clickhouse() -> None:
    units = lookup_units(FakeOrganisationDatabase(), limit=5)

    assert units is not None
    assert [(unit.id, unit.path) for unit in units] == [("unit-1", "Federal")]


def test_slow_org_unit_lookup_stops_waiting_at_the_time_limit() -> None:
    started = time.monotonic()

    units = lookup_units(FakeOrganisationDatabase(delay=2), limit=0.05)

    assert units is None
    assert time.monotonic() - started < 1


def tree_unit(
    unit_id: str, *above: str, closed: bool = False, leaf: bool = False
) -> OrgUnit:
    """A unit whose ancestors are listed from the top of the tree down."""
    chain = (*above, unit_id)
    return OrgUnit(
        unit_id,
        unit_id.title(),
        " › ".join(part.title() for part in chain),
        chain + (None,) * (7 - len(chain)),
        closed,
        level=len(chain),
        leaf=leaf,
    )


TOP = tree_unit("top")
REGION = tree_unit("region", "top")
ZONE = tree_unit("zone", "top", "region")
WOREDA = tree_unit("woreda", "top", "region", "zone")
FACILITY = tree_unit("facility", "top", "region", "zone", "woreda", leaf=True)
TREE = {unit.id: unit for unit in (TOP, REGION, ZONE, WOREDA, FACILITY)}


@pytest.fixture
def tree() -> Iterator[dict[str, Any]]:
    """Replace ClickHouse and the user table with an editable org-unit tree."""
    state: dict[str, Any] = {
        "units": dict(TREE),
        "users": {unit_id: {f"{unit_id}.user"} for unit_id in TREE},
    }
    with (
        mock.patch.object(
            routing,
            "get_units",
            side_effect=lambda ids: {
                i: state["units"][i] for i in ids if i in state["units"]
            },
        ),
        mock.patch.object(
            routing,
            "get_usernames_by_unit",
            side_effect=lambda ids: {i: state["users"].get(i, set()) for i in ids},
        ),
        mock.patch.object(
            routing,
            "get_top_units",
            side_effect=lambda: [u for u in state["units"].values() if u.level == 1],
        ),
        mock.patch.object(routing, "_active_handlers", side_effect=lambda n: set(n)),
    ):
        yield state


def test_feedback_goes_to_the_level_above(tree: dict[str, Any]) -> None:
    assert routing.find_destination_up(FACILITY, "facility.user") == WOREDA


def test_upward_route_skips_a_level_without_users(tree: dict[str, Any]) -> None:
    tree["users"]["woreda"] = set()

    assert routing.find_destination_up(FACILITY, "facility.user") == ZONE


def test_upward_route_skips_a_closed_level(tree: dict[str, Any]) -> None:
    tree["units"]["woreda"] = tree_unit("woreda", "top", "region", "zone", closed=True)

    assert routing.find_destination_up(FACILITY, "facility.user") == ZONE


def test_sender_in_a_closed_unit_routes_to_the_nearest_open_unit_above(
    tree: dict[str, Any],
) -> None:
    closed_origin = tree_unit(
        "facility", "top", "region", "zone", "woreda", closed=True
    )

    assert routing.find_destination_up(closed_origin, "facility.user") == WOREDA


def test_sender_is_not_counted_as_the_receiver(tree: dict[str, Any]) -> None:
    tree["users"]["woreda"] = {"sender.user"}

    assert routing.find_destination_up(FACILITY, "SENDER.user") == ZONE


def test_top_level_sender_goes_to_colleagues(tree: dict[str, Any]) -> None:
    tree["users"]["top"] = {"top.user", "colleague.user"}

    assert routing.find_destination_up(TOP, "top.user") == TOP


def test_lone_top_level_sender_has_nobody_to_receive(tree: dict[str, Any]) -> None:
    assert routing.find_destination_up(TOP, "top.user") is None


def test_sender_without_a_unit_goes_to_the_top_level(tree: dict[str, Any]) -> None:
    assert routing.find_destination_up(None, "someone") == TOP


def test_no_receiver_anywhere_above_returns_none(tree: dict[str, Any]) -> None:
    tree["users"] = {}

    assert routing.find_destination_up(FACILITY, "facility.user") is None


def test_feedback_goes_down_to_the_chosen_unit(tree: dict[str, Any]) -> None:
    assert routing.find_destination_down(REGION, FACILITY, "region.user") == FACILITY


def test_empty_downward_target_goes_to_the_nearest_unit_above_it(
    tree: dict[str, Any],
) -> None:
    tree["users"]["facility"] = set()

    assert routing.find_destination_down(REGION, FACILITY, "region.user") == WOREDA


def test_downward_route_never_goes_back_to_the_sender_level(
    tree: dict[str, Any],
) -> None:
    tree["users"]["woreda"] = set()
    tree["users"]["facility"] = set()

    assert routing.find_destination_down(ZONE, FACILITY, "zone.user") is None


def test_is_below() -> None:
    assert routing.is_below(REGION, FACILITY)
    assert not routing.is_below(FACILITY, REGION)
    assert not routing.is_below(REGION, REGION)
    assert not routing.is_below(WOREDA, tree_unit("other", "top", "region", "other-z"))


def test_ancestors_are_nearest_first() -> None:
    assert WOREDA.ancestor_ids == ("zone", "region", "top")
    assert TOP.ancestor_ids == ()


def test_describe_units_below_shows_who_receives(tree: dict[str, Any]) -> None:
    tree["users"]["facility"] = set()
    with mock.patch.object(
        routing, "search_units_below", return_value=[WOREDA, FACILITY]
    ):
        options = routing.describe_units_below(REGION, "w", "region.user", 20)

    assert [(o.unit.id, o.active_users, o.destination) for o in options] == [
        ("woreda", 1, WOREDA),
        ("facility", 0, WOREDA),
    ]


def test_upward_feedback_records_its_destination(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    submit(client, form_fields(client))

    saved = session.query(models[0]).one()
    assert saved.direction == "up"
    assert (saved.target_unit_id, saved.target_unit_name) == ("region", "Sample Region")
    assert saved.target_path == "Federal › Sample Region"
    assert [(a.unit_id, a.reason, a.is_current) for a in saved.unit_access] == [
        ("region", "target", True)
    ]
    routed = [e for e in saved.events if e.event_type == "routed"][0]
    assert (routed.to_unit_id, routed.message) == ("region", "Sample Region")
    assert routed.user_id is None


def test_routed_item_shows_where_it_went(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    submit(client, form_fields(client))
    saved = session.query(models[0]).one()

    listing = client.get("/moh/feedback/mine").get_data(as_text=True)
    detail = client.get(f"/moh/feedback/{saved.uuid}").get_data(as_text=True)

    assert "↑ Sample Region" in listing
    assert "Sent to Sample Region" in detail
    assert "Federal › Sample Region" in detail


def test_form_names_the_upper_level(client: FlaskClient) -> None:
    assert "Sample Region" in client.get("/moh/feedback/new").get_data(as_text=True)


@pytest.mark.parametrize("units", [[WOREDA]])
def test_feedback_can_be_sent_down_to_a_unit_below(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    with (
        mock.patch.object(views, "get_units", return_value={"facility": FACILITY}),
        mock.patch.object(views, "find_destination_down", return_value=FACILITY),
    ):
        response = submit(
            client,
            form_fields(client),
            direction="down",
            target_unit_id="facility",
        )

    assert response.status_code == 302
    saved = session.query(models[0]).one()
    assert (saved.direction, saved.target_unit_id) == ("down", "facility")


@pytest.mark.parametrize("units", [[ZONE]])
@pytest.mark.parametrize(
    ("found", "message"),
    [
        ({}, "Choose a unit below yours."),
        ({"facility": tree_unit("facility", "top", "region", "x")}, "below yours"),
        (
            {"facility": tree_unit("facility", "top", "region", "zone", closed=True)},
            "below yours",
        ),
    ],
)
def test_unit_outside_the_senders_area_is_refused(
    client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    found: dict[str, OrgUnit],
    message: str,
) -> None:
    with mock.patch.object(views, "get_units", return_value=found):
        response = submit(
            client,
            form_fields(client),
            direction="down",
            target_unit_id="facility",
        )

    assert response.status_code == 400
    assert message in response.get_data(as_text=True)
    assert session.query(models[0]).count() == 0


@pytest.mark.parametrize("units", [[WOREDA]])
def test_sending_down_requires_a_unit(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    assert submit(client, form_fields(client), direction="down").status_code == 400
    assert session.query(models[0]).count() == 0


@pytest.mark.parametrize("units", [[]])
def test_user_without_a_unit_cannot_send_down(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    response = submit(
        client, form_fields(client), direction="down", target_unit_id="facility"
    )

    assert response.status_code == 400
    assert session.query(models[0]).count() == 0
    assert 'value="down"' not in client.get("/moh/feedback/new").get_data(as_text=True)


@pytest.mark.parametrize("units", [[WOREDA]])
def test_downward_target_with_nobody_to_receive_is_refused(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    with (
        mock.patch.object(views, "get_units", return_value={"facility": FACILITY}),
        mock.patch.object(views, "find_destination_down", return_value=None),
    ):
        response = submit(
            client, form_fields(client), direction="down", target_unit_id="facility"
        )

    assert response.status_code == 400
    assert session.query(models[0]).count() == 0


def test_unknown_direction_is_refused(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    assert submit(client, form_fields(client), direction="sideways").status_code == 400
    assert session.query(models[0]).count() == 0


def test_feedback_is_saved_for_routing_later_when_the_lookup_fails(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    with mock.patch.object(views, "get_user_units", return_value=None):
        fields = form_fields(client)
        assert submit(client, fields).status_code == 302

    saved = session.query(models[0]).one()
    assert saved.target_unit_id is None
    assert saved.unit_access == []
    assert [e.event_type for e in saved.events] == ["created", "routing_pending"]
    assert "Waiting for an office" in client.get("/moh/feedback/mine").get_data(
        as_text=True
    )


def test_feedback_is_saved_for_routing_later_when_routing_fails(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    fields = form_fields(client)
    with mock.patch.object(
        views, "find_destination_up", side_effect=OrgUnitLookupError("down")
    ):
        assert submit(client, fields).status_code == 302

    assert session.query(models[0]).one().target_unit_id is None


@pytest.mark.parametrize("units", [[WOREDA]])
def test_sending_down_while_the_lookup_fails_is_refused_with_the_message_kept(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    fields = form_fields(client)
    with mock.patch.object(views, "get_units", side_effect=OrgUnitLookupError("x")):
        response = submit(client, fields, direction="down", target_unit_id="facility")

    assert response.status_code == 503
    assert MESSAGE in response.get_data(as_text=True)
    assert session.query(models[0]).count() == 0


@pytest.mark.parametrize("units", [[WOREDA]])
def test_unit_search_returns_the_units_below(client: FlaskClient) -> None:
    option = routing.UnitOption(FACILITY, 1, FACILITY)
    with mock.patch.object(
        views, "describe_units_below", return_value=[option]
    ) as find:
        data = client.get("/moh/feedback/units?q=fac").get_json()

    assert find.call_args.args[:2] == (WOREDA, "fac")
    assert data["result"] == [
        {
            "id": "facility",
            "name": "Facility",
            "path": FACILITY.path,
            "active_users": 1,
            "goes_to": "Facility",
        }
    ]


@pytest.mark.parametrize("units", [[WOREDA]])
def test_unit_search_needs_at_least_two_letters(client: FlaskClient) -> None:
    assert client.get("/moh/feedback/units?q=a").get_json() == {"result": []}


@pytest.mark.parametrize("units", [[WOREDA]])
def test_unit_search_reports_when_unavailable(client: FlaskClient) -> None:
    with mock.patch.object(
        views, "describe_units_below", side_effect=OrgUnitLookupError("x")
    ):
        assert client.get("/moh/feedback/units?q=fac").status_code == 503


def test_unit_search_requires_login(client: FlaskClient, user: SimpleNamespace) -> None:
    user.is_authenticated = False

    assert client.get("/moh/feedback/units?q=fac").status_code == 401


@pytest.mark.parametrize("units", [[FACILITY]])
def test_leaf_unit_is_not_offered_sending_down(client: FlaskClient) -> None:
    assert 'value="down"' not in client.get("/moh/feedback/new").get_data(as_text=True)


def sent_to(
    session: Session,
    models: tuple[Any, Any],
    unit_id: str = "unit-1",
    owner: int | None = 8,
    is_current: bool = True,
    message: str = MESSAGE,
) -> Any:
    item = add_item(session, models, owner, message)
    access_model = models[0].unit_access.property.mapper.class_
    item.unit_access.append(
        access_model(unit_id=unit_id, reason="target", is_current=is_current)
    )
    session.commit()
    return item


def waiting_html(client: FlaskClient) -> str:
    return client.get("/moh/feedback/waiting").get_data(as_text=True)


def test_waiting_lists_items_sent_to_the_users_unit(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    sent_to(session, models, message="Sent to my own unit here")
    sent_to(session, models, unit_id="unit-9", message="Sent to another unit here")

    html = waiting_html(client)

    assert "Sent to my own unit here" in html
    assert "Sent to another unit here" not in html


def test_waiting_hides_the_users_own_feedback(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    sent_to(session, models, owner=7, message="Written by this same user")

    assert "Written by this same user" not in waiting_html(client)


def test_waiting_keeps_items_from_deleted_accounts(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    sent_to(session, models, owner=None, message="Sender account was deleted")

    assert "Sender account was deleted" in waiting_html(client)


def test_waiting_leaves_out_items_that_moved_on(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    sent_to(session, models, is_current=False, message="Moved to another level")

    assert "Moved to another level" not in waiting_html(client)


def test_waiting_shows_oldest_first(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    newer = sent_to(session, models, message="The newer waiting item")
    older = sent_to(session, models, message="The older waiting item")
    older.created_on = newer.created_on - timedelta(days=1)
    session.flush()

    html = waiting_html(client)

    assert html.index("The older waiting item") < html.index("The newer waiting item")


def test_waiting_empty_state(client: FlaskClient) -> None:
    assert "Nothing is waiting on you." in waiting_html(client)


def test_handler_can_open_an_item_sent_to_their_unit(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)

    response = client.get(f"/moh/feedback/{item.uuid}")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert MESSAGE in html
    assert "Sample User" in html
    assert "Your message" not in html
    assert "Back to Waiting on me" in html


def test_earlier_unit_can_still_read_an_item_that_moved_on(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models, is_current=False)

    assert client.get(f"/moh/feedback/{item.uuid}").status_code == 200


def test_user_at_another_unit_cannot_open_the_item(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models, unit_id="unit-9")

    assert client.get(f"/moh/feedback/{item.uuid}").status_code == 404


def test_user_without_a_handler_role_cannot_see_items_or_the_tab(
    client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = sent_to(session, models)
    user.roles = [SimpleNamespace(name="MoHUsageViewer")]

    assert client.get("/moh/feedback/waiting").status_code == 404
    assert client.get(f"/moh/feedback/{item.uuid}").status_code == 404
    assert "Waiting on me" not in client.get("/moh/feedback/mine").get_data(
        as_text=True
    )


def test_handler_sees_the_waiting_tab(client: FlaskClient) -> None:
    assert "Waiting on me" in client.get("/moh/feedback/mine").get_data(as_text=True)


def test_sender_can_read_their_item_without_a_handler_role(
    client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = sent_to(session, models, owner=7, unit_id="unit-9")
    user.roles = []

    html = client.get(f"/moh/feedback/{item.uuid}").get_data(as_text=True)

    assert "Your message" in html


def test_access_is_refused_rather_than_guessed_when_units_are_unknown(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)
    with mock.patch.object(views, "get_user_units", return_value=None):
        assert client.get("/moh/feedback/waiting").status_code == 503
        assert client.get(f"/moh/feedback/{item.uuid}").status_code == 503


def test_waiting_follows_the_feature_setting_and_login(
    client: FlaskClient, user: SimpleNamespace
) -> None:
    user.is_authenticated = False
    assert client.get("/moh/feedback/waiting").status_code == 302

    client.application.config["MOH_FEEDBACK_ENABLED"] = False
    assert client.get("/moh/feedback/waiting").status_code == 404


def test_form_says_colleagues_when_the_sender_has_no_level_above(
    client: FlaskClient,
) -> None:
    with mock.patch.object(views, "find_destination_up", return_value=UNIT):
        html = client.get("/moh/feedback/new").get_data(as_text=True)

    assert "(my colleagues)" in html
    assert "(my upper level)" not in html


HANDLERS = [Person(7, "Sample User"), Person(9, "Other Handler")]


@pytest.fixture
def handled_client(client: FlaskClient) -> Iterator[FlaskClient]:
    with mock.patch.object(views, "unit_handlers", return_value=list(HANDLERS)):
        yield client


def page_fields(client: FlaskClient, item: Any) -> dict[str, str]:
    html = client.get(f"/moh/feedback/{item.uuid}").get_data(as_text=True)
    return {
        "csrf_token": _hidden_value(html, "csrf_token"),
        "expected_status": item.status,
    }


def act(client: FlaskClient, item: Any, action: str, **extra: str) -> Any:
    data = {**page_fields(client, item), "action": action, **extra}
    return client.post(f"/moh/feedback/{item.uuid}/action", data=data)


def history(item: Any) -> list[str]:
    return [event.event_type for event in item.events]


def test_handler_can_start_a_review(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)

    assert act(handled_client, item, "start_review").status_code == 302

    assert item.status == "in_review"
    assert item.first_response_on is None
    assert history(item)[-1] == "review_started"


def test_handler_can_assign_to_someone_in_their_unit(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)

    assert act(handled_client, item, "assign", assignee_id="9").status_code == 302

    assert item.status == "assigned"
    assert (item.assigned_to_fk, item.assignee_name) == (9, "Other Handler")
    assert item.first_response_on is not None


def test_cannot_assign_to_someone_outside_the_unit(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)

    assert act(handled_client, item, "assign", assignee_id="99").status_code == 400
    assert item.status == "new"


def test_answering_assigns_the_item_to_whoever_answered(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)

    assert act(handled_client, item, "answer", message="Corrected.").status_code == 302

    assert item.status == "answered"
    assert (item.assigned_to_fk, item.assignee_name) == (7, "Sample User")
    assert item.answered_on is not None
    assert item.events[-1].message == "Corrected."


def test_answering_keeps_an_existing_assignee(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)
    act(handled_client, item, "assign", assignee_id="9")

    act(handled_client, item, "answer", message="Corrected.")

    assert item.assigned_to_fk == 9


def test_declining_closes_the_item_with_the_reason(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)

    assert (
        act(handled_client, item, "decline", message="Out of scope.").status_code == 302
    )

    assert (item.status, item.closure_reason) == ("closed", "declined")
    assert item.closed_on is not None
    assert item.display_status == "declined"
    assert "Declined" in handled_client.get(f"/moh/feedback/{item.uuid}").get_data(
        as_text=True
    )


@pytest.mark.parametrize("action", ["ask", "answer", "decline", "note"])
def test_message_is_required(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    action: str,
) -> None:
    item = sent_to(session, models)

    assert act(handled_client, item, action, message="   ").status_code == 400
    assert history(item) == ["created"]


def test_message_cannot_be_too_long(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)

    assert act(handled_client, item, "answer", message="x" * 2001).status_code == 400
    assert item.status == "new"


def test_unknown_action_is_refused(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)

    assert act(handled_client, item, "delete").status_code == 400


def test_action_not_allowed_in_this_status_is_refused(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)
    act(handled_client, item, "answer", message="Done.")

    assert act(handled_client, item, "decline", message="No.").status_code == 409
    assert item.status == "answered"


def test_second_person_acting_on_a_stale_page_is_told(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)
    stale = page_fields(handled_client, item)
    act(handled_client, item, "answer", message="First answer.")

    response = handled_client.post(
        f"/moh/feedback/{item.uuid}/action",
        data={**stale, "action": "ask", "message": "Second person."},
    )

    assert response.status_code == 409
    html = response.get_data(as_text=True)
    assert "This item has changed" in html
    assert "Second person." in html
    assert item.status == "answered"


def test_forged_form_is_refused(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)

    response = handled_client.post(
        f"/moh/feedback/{item.uuid}/action",
        data={
            "csrf_token": "forged",
            "expected_status": "new",
            "action": "start_review",
        },
    )

    assert response.status_code == 400
    assert item.status == "new"


def test_sender_cannot_handle_their_own_item(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models, owner=7)

    response = handled_client.post(
        f"/moh/feedback/{item.uuid}/action",
        data={
            "csrf_token": form_fields(handled_client)["csrf_token"],
            "expected_status": "new",
            "action": "start_review",
        },
    )

    assert response.status_code == 403
    assert item.status == "new"


def test_earlier_unit_can_read_but_not_act(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models, is_current=False)

    html = handled_client.get(f"/moh/feedback/{item.uuid}").get_data(as_text=True)
    assert 'value="answer"' not in html
    assert (
        handled_client.post(
            f"/moh/feedback/{item.uuid}/action",
            data={"action": "start_review"},
        ).status_code
        == 403
    )


def test_user_at_another_unit_cannot_act(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models, unit_id="unit-9")

    response = handled_client.post(
        f"/moh/feedback/{item.uuid}/action", data={"action": "start_review"}
    )

    assert response.status_code == 404


def test_sender_never_sees_internal_notes(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = sent_to(session, models)
    act(handled_client, item, "note", message="Secret handler note.")
    assert "Secret handler note." in handled_client.get(
        f"/moh/feedback/{item.uuid}"
    ).get_data(as_text=True)

    user.id = 8
    html = handled_client.get(f"/moh/feedback/{item.uuid}").get_data(as_text=True)

    assert "Secret handler note." not in html
    assert "Internal note" not in html


def test_sender_can_reply_when_asked_and_item_returns_to_review(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = sent_to(session, models)
    act(handled_client, item, "ask", message="Which month?")
    user.id = 8
    html = handled_client.get(f"/moh/feedback/{item.uuid}").get_data(as_text=True)
    assert "Which month?" in html

    response = handled_client.post(
        f"/moh/feedback/{item.uuid}/reply",
        data={"csrf_token": _hidden_value(html, "csrf_token"), "message": "Meskerem."},
    )

    assert response.status_code == 302
    assert item.status == "in_review"
    assert (item.events[-1].event_type, item.events[-1].message) == (
        "sender_reply",
        "Meskerem.",
    )


def test_sender_can_add_information_when_not_asked(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = sent_to(session, models)
    user.id = 8
    html = handled_client.get(f"/moh/feedback/{item.uuid}").get_data(as_text=True)
    assert "Your reply" not in html
    assert "Add more information" in html

    response = handled_client.post(
        f"/moh/feedback/{item.uuid}/reply",
        data={
            "csrf_token": form_fields(handled_client)["csrf_token"],
            "message": "One more detail.",
        },
    )

    assert response.status_code == 302
    assert item.status == "new"
    assert (item.events[-1].event_type, item.events[-1].message) == (
        "sender_message",
        "One more detail.",
    )


def test_handler_cannot_use_the_sender_reply(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)

    response = handled_client.post(
        f"/moh/feedback/{item.uuid}/reply", data={"message": "Hello."}
    )

    assert response.status_code == 404


def test_waiting_shows_only_what_needs_this_user(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    mine = sent_to(session, models, message="Assigned to this handler")
    other = sent_to(session, models, message="Assigned to someone else")
    asked = sent_to(session, models, message="Waiting on the sender")
    act(handled_client, mine, "assign", assignee_id="7")
    act(handled_client, other, "assign", assignee_id="9")
    act(handled_client, asked, "ask", message="Which month?")

    needs_action = waiting_html(handled_client)
    everything = handled_client.get("/moh/feedback/waiting?view=all").get_data(
        as_text=True
    )

    assert "Assigned to this handler" in needs_action
    assert "Assigned to someone else" not in needs_action
    assert "Waiting on the sender" not in needs_action
    assert "Assigned to someone else" in everything
    assert "Waiting on the sender" in everything


def test_action_buttons_match_the_status(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)
    act(handled_client, item, "decline", message="No.")

    html = handled_client.get(f"/moh/feedback/{item.uuid}").get_data(as_text=True)

    assert 'value="answer"' not in html
    assert 'value="note"' not in html


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("new", {"start_review", *HANDLING_ACTIONS}),
        ("in_review", HANDLING_ACTIONS),
        ("assigned", HANDLING_ACTIONS),
        ("needs_info", {"note", "reply", "set_priority"}),
        ("answered", {"note", "reply"}),
        ("closed", set()),
    ],
)
def test_allowed_actions(status: str, expected: set[str]) -> None:
    assert allowed_actions(status) == expected


def answered_item(
    client: FlaskClient, session: Session, models: tuple[Any, Any], user: Any
) -> Any:
    """Return an item answered by a handler, with the sender signed in."""
    item = sent_to(session, models)
    act(client, item, "answer", message="Corrected the figure.")
    user.id = 8
    return item


def decide(client: FlaskClient, item: Any, decision: str, message: str = "") -> Any:
    html = client.get(f"/moh/feedback/{item.uuid}").get_data(as_text=True)
    return client.post(
        f"/moh/feedback/{item.uuid}/confirm",
        data={
            "csrf_token": _hidden_value(html, "csrf_token"),
            "decision": decision,
            "message": message,
        },
    )


def test_sender_is_asked_whether_the_answer_solved_it(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = answered_item(handled_client, session, models, user)

    html = handled_client.get(f"/moh/feedback/{item.uuid}").get_data(as_text=True)

    assert "Yes, this solved it" in html
    assert "No, not solved" in html


def test_handler_is_not_asked_whether_the_answer_solved_it(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)
    act(handled_client, item, "answer", message="Corrected the figure.")

    html = handled_client.get(f"/moh/feedback/{item.uuid}").get_data(as_text=True)

    assert "Yes, this solved it" not in html


def test_sender_is_not_asked_before_an_answer(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = sent_to(session, models)
    user.id = 8

    html = handled_client.get(f"/moh/feedback/{item.uuid}").get_data(as_text=True)

    assert "Yes, this solved it" not in html


def test_solved_closes_the_item(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = answered_item(handled_client, session, models, user)

    assert decide(handled_client, item, "solved").status_code == 302

    assert (item.status, item.closure_reason) == ("closed", "confirmed")
    assert item.closed_on is not None
    assert item.answered_on is not None
    assert history(item)[-1] == "sender_solved"
    assert item.events[-1].message is None
    html = handled_client.get(f"/moh/feedback/{item.uuid}").get_data(as_text=True)
    assert '<span class="status">Closed</span>' in html
    assert "Yes, this solved it" not in html


def test_solved_keeps_an_optional_comment(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = answered_item(handled_client, session, models, user)

    decide(handled_client, item, "solved", "Thank you, it is right.")

    assert item.events[-1].message == "Thank you, it is right."


def test_not_solved_returns_the_item_to_the_unit(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = answered_item(handled_client, session, models, user)

    assert decide(handled_client, item, "not_solved", "Still wrong.").status_code == 302

    assert item.status == "in_review"
    assert item.closure_reason is None
    assert item.closed_on is None
    assert item.answered_on is None
    assert (item.events[-1].event_type, item.events[-1].message) == (
        "sender_not_solved",
        "Still wrong.",
    )
    user.id = 9
    assert MESSAGE in waiting_html(handled_client)
    html = handled_client.get(f"/moh/feedback/{item.uuid}").get_data(as_text=True)
    assert "Still wrong." in html
    assert 'value="answer"' in html


def test_not_solved_can_repeat_until_the_sender_is_satisfied(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = answered_item(handled_client, session, models, user)

    decide(handled_client, item, "not_solved", "First reason.")
    user.id = 7
    act(handled_client, item, "answer", message="Second answer.")
    assert item.answered_on is not None
    user.id = 8
    decide(handled_client, item, "not_solved", "Second reason.")
    user.id = 7
    act(handled_client, item, "answer", message="Third answer.")
    user.id = 8
    decide(handled_client, item, "solved")

    assert item.status == "closed"
    assert history(item)[-6:] == [
        "answered",
        "sender_not_solved",
        "answered",
        "sender_not_solved",
        "answered",
        "sender_solved",
    ]


@pytest.mark.parametrize("message", ["", "   ", "\r\n"])
def test_not_solved_needs_a_reason(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
    message: str,
) -> None:
    item = answered_item(handled_client, session, models, user)

    response = decide(handled_client, item, "not_solved", message)

    assert response.status_code == 400
    assert "Please say why" in response.get_data(as_text=True)
    assert item.status == "answered"


@pytest.mark.parametrize("decision", ["solved", "not_solved"])
def test_decision_comment_cannot_be_too_long(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
    decision: str,
) -> None:
    item = answered_item(handled_client, session, models, user)

    assert decide(handled_client, item, decision, "x" * 2001).status_code == 400
    assert item.status == "answered"


@pytest.mark.parametrize("decision", ["", "maybe"])
def test_decision_must_be_yes_or_no(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
    decision: str,
) -> None:
    item = answered_item(handled_client, session, models, user)

    assert decide(handled_client, item, decision, "Some text.").status_code == 400
    assert item.status == "answered"


def test_decision_refused_after_it_was_already_made(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = answered_item(handled_client, session, models, user)
    stale = form_fields(handled_client)["csrf_token"]
    decide(handled_client, item, "solved")

    response = handled_client.post(
        f"/moh/feedback/{item.uuid}/confirm",
        data={
            "csrf_token": stale,
            "decision": "not_solved",
            "message": "Changed my mind.",
        },
    )

    assert response.status_code == 409
    assert "This item has changed" in response.get_data(as_text=True)
    assert item.status == "closed"
    assert history(item).count("sender_solved") == 1
    assert "sender_not_solved" not in history(item)


@pytest.mark.parametrize("action", ["ask", "decline"])
def test_decision_refused_when_there_is_no_answer(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
    action: str,
) -> None:
    item = sent_to(session, models)
    act(handled_client, item, action, message="Handler message.")
    status = item.status
    user.id = 8

    response = handled_client.post(
        f"/moh/feedback/{item.uuid}/confirm",
        data={
            "csrf_token": form_fields(handled_client)["csrf_token"],
            "decision": "solved",
        },
    )

    assert response.status_code == 409
    assert item.status == status


def test_handler_cannot_decide_for_the_sender(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)
    act(handled_client, item, "answer", message="Corrected the figure.")

    response = handled_client.post(
        f"/moh/feedback/{item.uuid}/confirm",
        data={
            "csrf_token": form_fields(handled_client)["csrf_token"],
            "decision": "solved",
        },
    )

    assert response.status_code == 404
    assert item.status == "answered"


def test_forged_decision_is_refused_and_keeps_the_draft(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = answered_item(handled_client, session, models, user)

    response = handled_client.post(
        f"/moh/feedback/{item.uuid}/confirm",
        data={
            "csrf_token": "forged",
            "decision": "not_solved",
            "message": "My long explanation.",
        },
    )

    assert response.status_code == 400
    assert "My long explanation." in response.get_data(as_text=True)
    assert item.status == "answered"


def test_decision_needs_a_sign_in(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = answered_item(handled_client, session, models, user)
    user.is_authenticated = False

    response = handled_client.post(
        f"/moh/feedback/{item.uuid}/confirm", data={"decision": "solved"}
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/login/"
    assert item.status == "answered"


def test_decision_is_hidden_when_the_feature_is_off(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = answered_item(handled_client, session, models, user)
    handled_client.application.config["MOH_FEEDBACK_ENABLED"] = False

    response = handled_client.post(
        f"/moh/feedback/{item.uuid}/confirm", data={"decision": "solved"}
    )

    assert response.status_code == 404
    assert item.status == "answered"


HANA = SimpleNamespace(
    id=20,
    username="hana.t",
    email="Hana.Tesfaye@example.org",
    first_name="Hana",
    last_name="Tesfaye",
)
HANA_TWO = SimpleNamespace(
    id=21,
    username="hana.other",
    email="hana.other@example.org",
    first_name="HANA",
    last_name="tesfaye",
)
NO_UNIT = SimpleNamespace(
    id=22,
    username="no.unit",
    email="no.unit@example.org",
    first_name="Dawit",
    last_name="Alemu",
)
GEEZ = SimpleNamespace(
    id=23,
    username="geez.name",
    email="geez@example.org",
    first_name="ሀና",
    last_name="ተስፋዬ",
)
ME = SimpleNamespace(
    id=7,
    username="sample.user",
    email="sample.user@example.org",
    first_name="Sample",
    last_name="User",
)
PERSON_UNITS = {
    "hana.t": [UNIT, OTHER_UNIT],
    "hana.other": [PARENT_UNIT, CLOSED_UNIT],
    "no.unit": [],
    "geez.name": [UNIT],
}


@pytest.fixture
def people_client(handled_client: FlaskClient) -> Iterator[FlaskClient]:
    accounts = [HANA, HANA_TWO, NO_UNIT, GEEZ, ME]
    with (
        mock.patch.object(people, "active_accounts", return_value=accounts),
        mock.patch.object(
            people, "get_user_units", side_effect=PERSON_UNITS.__getitem__
        ),
        mock.patch.object(
            views,
            "active_user_ids",
            side_effect=lambda ids: {i for i in ids if i in {20, 21, 22, 23}},
        ),
    ):
        yield handled_client


def search(client: FlaskClient, term: str) -> Any:
    return client.post(
        "/moh/feedback/people/search",
        data={"csrf_token": form_fields(client)["csrf_token"], "q": term},
    )


def found(client: FlaskClient, term: str) -> list[dict[str, Any]]:
    return search(client, term).get_json()["result"]


def token_of(client: FlaskClient, term: str, index: int = 0) -> str:
    return found(client, term)[index]["token"]


def add_person(client: FlaskClient, item: Any, token: str) -> Any:
    return client.post(
        f"/moh/feedback/{item.uuid}/participants",
        data={"csrf_token": form_fields(client)["csrf_token"], "person_token": token},
    )


def send_with(client: FlaskClient, tokens: list[str], **extra: str) -> Any:
    data: dict[str, Any] = {
        **form_fields(client),
        "type": "problem",
        "message": MESSAGE,
        "direction": "up",
        "person_token": tokens,
        **extra,
    }
    return client.post("/moh/feedback/", data=data)


def added_item(
    client: FlaskClient, session: Session, models: tuple[Any, Any], user: Any
) -> Any:
    """Return an item with Hana added by its handler, with Hana signed in."""
    item = sent_to(session, models)
    with mock.patch.object(views, "get_user_units", return_value=[UNIT]):
        assert add_person(client, item, token_of(client, "hana.t")).status_code == 302
    user.id = 20
    return item


def detail(client: FlaskClient, item: Any) -> Any:
    return client.get(f"/moh/feedback/{item.uuid}")


@pytest.mark.parametrize(
    "term",
    [
        "Hana.Tesfaye@example.org",
        "HANA.TESFAYE@EXAMPLE.ORG",
        "  hana.t ",
        "HANA.T",
    ],
)
def test_search_finds_exact_email_or_username_in_any_capitalisation(
    people_client: FlaskClient, term: str
) -> None:
    assert [person["name"] for person in found(people_client, term)] == ["Hana Tesfaye"]


@pytest.mark.parametrize(
    "term", ["Hana Tesfaye", "tesfaye hana", "  HANA    Tesfaye ", "ｈａｎａ tesfaye"]
)
def test_search_finds_first_and_last_name_in_either_order(
    people_client: FlaskClient, term: str
) -> None:
    assert len(found(people_client, term)) == 2


def test_search_finds_names_in_geez_script(people_client: FlaskClient) -> None:
    assert [person["name"] for person in found(people_client, "ሀና ተስፋዬ")] == ["ሀና ተስፋዬ"]


@pytest.mark.parametrize(
    "term",
    ["Han", "Hana", "Tesfaye", "hana.tesfaye", "example.org", "Hana Tesfay", "Hana T"],
)
def test_partial_text_finds_nobody(people_client: FlaskClient, term: str) -> None:
    assert found(people_client, term) == []


def test_search_shows_name_and_path_but_no_account_details(
    people_client: FlaskClient,
) -> None:
    result = found(people_client, "Hana.Tesfaye@example.org")

    assert result[0]["paths"] == [UNIT.path, OTHER_UNIT.path]
    assert set(result[0]) == {"token", "name", "paths"}
    assert "example.org" not in str(search(people_client, "hana.t").get_data())


def test_search_leaves_out_closed_units_when_an_open_one_exists(
    people_client: FlaskClient,
) -> None:
    assert found(people_client, "hana.other")[0]["paths"] == [PARENT_UNIT.path]


def test_search_returns_no_path_for_someone_without_a_unit(
    people_client: FlaskClient,
) -> None:
    assert found(people_client, "no.unit")[0]["paths"] == []


def test_search_never_finds_the_searcher(people_client: FlaskClient) -> None:
    assert found(people_client, "sample.user") == []


def test_search_is_unavailable_when_a_path_cannot_be_read(
    people_client: FlaskClient,
) -> None:
    with mock.patch.object(people, "get_user_units", return_value=None):
        response = search(people_client, "hana.t")

    assert response.status_code == 503


def test_search_is_limited_and_the_limit_passes(
    people_client: FlaskClient, session: Session
) -> None:
    people_client.application.config["MOH_FEEDBACK_MAX_PERSON_SEARCHES"] = 2
    assert search(people_client, "hana.t").status_code == 200
    assert search(people_client, "no.unit").status_code == 200

    assert search(people_client, "hana.t").status_code == 429

    for row in session.query(_search_model()):
        row.searched_on = datetime.utcnow() - timedelta(minutes=11)
    session.commit()
    assert search(people_client, "hana.t").status_code == 200
    assert session.query(_search_model()).count() == 1


def test_search_too_short_is_not_counted(
    people_client: FlaskClient, session: Session
) -> None:
    assert found(people_client, " a ") == []
    assert session.query(_search_model()).count() == 0


def test_search_refuses_a_forged_form(people_client: FlaskClient) -> None:
    response = people_client.post(
        "/moh/feedback/people/search", data={"csrf_token": "x", "q": "hana.t"}
    )

    assert response.status_code == 400


def test_search_needs_a_sign_in(
    people_client: FlaskClient, user: SimpleNamespace
) -> None:
    user.is_authenticated = False

    assert (
        people_client.post(
            "/moh/feedback/people/search", data={"q": "hana.t"}
        ).status_code
        == 401
    )


def test_search_is_hidden_when_the_feature_is_off(people_client: FlaskClient) -> None:
    people_client.application.config["MOH_FEEDBACK_ENABLED"] = False

    assert (
        people_client.post(
            "/moh/feedback/people/search", data={"q": "hana.t"}
        ).status_code
        == 404
    )


def test_form_offers_to_add_a_person(people_client: FlaskClient) -> None:
    html = people_client.get("/moh/feedback/new").get_data(as_text=True)

    assert "Add a person (optional)" in html
    assert "This person will be able to read this feedback and reply." in html


def test_person_added_when_sending_is_saved_with_their_path(
    people_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    token = token_of(people_client, "hana.t")

    assert send_with(people_client, [token]).status_code == 302

    item = session.query(models[0]).one()
    row = item.active_participants[0]
    assert (row.user_id, row.added_by_fk, row.display_name) == (20, 7, "Hana Tesfaye")
    assert row.unit_path == f"{UNIT.path}\n{OTHER_UNIT.path}"
    assert history(item)[-1] == "person_added"
    assert item.events[-1].message == f"Hana Tesfaye · {UNIT.path} · {OTHER_UNIT.path}"
    assert item.status == "new"
    assert item.assigned_to_fk is None


def test_sending_without_a_person_adds_nobody(
    people_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    send_with(people_client, [])

    assert session.query(models[0]).one().participants == []


def test_same_person_selected_twice_is_added_once(
    people_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    tokens = [token_of(people_client, "hana.t"), token_of(people_client, "HANA.T")]

    send_with(people_client, tokens)

    assert len(session.query(models[0]).one().participants) == 1


def test_selected_people_survive_a_form_error(people_client: FlaskClient) -> None:
    token = token_of(people_client, "hana.t")

    response = send_with(people_client, [token], message="short")

    assert response.status_code == 400
    assert token in response.get_data(as_text=True)


@pytest.mark.parametrize("bad_token", ["forged", ""])
def test_unreadable_person_stops_the_send(
    people_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    bad_token: str,
) -> None:
    response = send_with(people_client, [bad_token])

    assert response.status_code == 400
    assert "Please search again" in response.get_data(as_text=True)
    assert session.query(models[0]).count() == 0


def test_token_from_another_searcher_is_refused(
    people_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    token = token_of(people_client, "hana.t")
    user.id = 8

    assert send_with(people_client, [token]).status_code == 400
    assert session.query(models[0]).count() == 0


def test_expired_token_is_refused(people_client: FlaskClient) -> None:
    token = token_of(people_client, "hana.t")
    with (
        people_client.application.app_context(),
        mock.patch.object(people, "_TOKEN_MAX_AGE_SECONDS", -1),
    ):
        assert people.read_person_token(token, 7) is None


def test_cannot_add_too_many_people_when_sending(
    people_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    people_client.application.config["MOH_FEEDBACK_MAX_PEOPLE_PER_ITEM"] = 1
    tokens = [token_of(people_client, "hana.t"), token_of(people_client, "no.unit")]

    response = send_with(people_client, tokens)

    assert response.status_code == 400
    assert "up to 1 people" in response.get_data(as_text=True)
    assert session.query(models[0]).count() == 0


def test_daily_limit_on_adding_people(
    people_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    people_client.application.config["MOH_FEEDBACK_MAX_PEOPLE_ADDED_PER_DAY"] = 1
    first = sent_to(session, models)
    second = sent_to(session, models)
    assert (
        add_person(people_client, first, token_of(people_client, "hana.t")).status_code
        == 302
    )

    response = add_person(people_client, second, token_of(people_client, "no.unit"))

    assert response.status_code == 400
    assert "many people today" in response.get_data(as_text=True)


def test_deactivated_person_cannot_be_added(
    people_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)
    token = token_of(people_client, "hana.t")

    with mock.patch.object(views, "active_user_ids", return_value=set()):
        response = add_person(people_client, item, token)

    assert response.status_code == 400
    assert item.participants == []


def test_added_person_can_read_but_sees_no_internal_notes(
    people_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = sent_to(session, models)
    act(people_client, item, "note", message="Secret handler note.")
    add_person(people_client, item, token_of(people_client, "hana.t"))
    user.id = 20
    user.username = "hana.t"
    with mock.patch.object(views, "get_user_units", return_value=[OTHER_UNIT]):
        html = detail(people_client, item).get_data(as_text=True)

    assert MESSAGE in html
    assert "Secret handler note." not in html
    assert 'value="answer"' not in html
    assert 'id="person-search"' not in html
    assert "Not for me" in html


def test_added_person_without_a_handler_role_can_read(
    people_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = added_item(people_client, session, models, user)
    user.roles = [SimpleNamespace(name="Gamma")]

    assert detail(people_client, item).status_code == 200


def test_added_person_can_read_while_units_are_unavailable(
    people_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = added_item(people_client, session, models, user)

    with mock.patch.object(views, "get_user_units", return_value=None):
        assert detail(people_client, item).status_code == 200


def test_added_person_who_also_handles_the_unit_keeps_handling(
    people_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = added_item(people_client, session, models, user)

    html = detail(people_client, item).get_data(as_text=True)

    assert 'value="answer"' in html
    assert "Add a comment" not in html


@pytest.fixture
def outside_unit() -> Iterator[None]:
    with mock.patch.object(views, "get_user_units", return_value=[OTHER_UNIT]):
        yield


def test_added_person_cannot_handle_the_item(
    people_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
    outside_unit: None,
) -> None:
    item = added_item(people_client, session, models, user)

    response = people_client.post(
        f"/moh/feedback/{item.uuid}/action", data={"action": "start_review"}
    )

    assert response.status_code == 403
    assert item.status == "new"


def test_added_person_cannot_confirm_for_the_sender(
    people_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
    outside_unit: None,
) -> None:
    item = sent_to(session, models)
    with mock.patch.object(views, "get_user_units", return_value=[UNIT]):
        add_person(people_client, item, token_of(people_client, "hana.t"))
        act(people_client, item, "answer", message="Corrected.")
    user.id = 20

    assert "Yes, this solved it" not in detail(people_client, item).get_data(
        as_text=True
    )
    response = people_client.post(
        f"/moh/feedback/{item.uuid}/confirm", data={"decision": "solved"}
    )
    assert response.status_code == 404
    assert item.status == "answered"


def test_added_person_cannot_add_others(
    people_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
    outside_unit: None,
) -> None:
    item = added_item(people_client, session, models, user)

    response = add_person(people_client, item, token_of(people_client, "no.unit"))

    assert response.status_code == 403
    assert len(item.active_participants) == 1


def test_added_person_can_comment_without_changing_the_status(
    people_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
    outside_unit: None,
) -> None:
    item = added_item(people_client, session, models, user)
    html = detail(people_client, item).get_data(as_text=True)

    response = people_client.post(
        f"/moh/feedback/{item.uuid}/reply",
        data={"csrf_token": _hidden_value(html, "csrf_token"), "message": "I saw it."},
    )

    assert response.status_code == 302
    assert item.status == "new"
    assert (item.events[-1].event_type, item.events[-1].message) == (
        "participant_comment",
        "I saw it.",
    )


def test_added_person_comment_does_not_answer_a_question(
    people_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
    outside_unit: None,
) -> None:
    item = sent_to(session, models)
    with mock.patch.object(views, "get_user_units", return_value=[UNIT]):
        add_person(people_client, item, token_of(people_client, "hana.t"))
        act(people_client, item, "ask", message="Which month?")
    user.id = 20

    people_client.post(
        f"/moh/feedback/{item.uuid}/reply",
        data={
            "csrf_token": form_fields(people_client)["csrf_token"],
            "message": "Not sure.",
        },
    )

    assert item.status == "needs_info"


def test_added_person_cannot_comment_once_closed(
    people_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
    outside_unit: None,
) -> None:
    item = sent_to(session, models)
    with mock.patch.object(views, "get_user_units", return_value=[UNIT]):
        add_person(people_client, item, token_of(people_client, "hana.t"))
        act(people_client, item, "decline", message="Out of scope.")
    user.id = 20
    assert "Add a comment" not in detail(people_client, item).get_data(as_text=True)

    response = people_client.post(
        f"/moh/feedback/{item.uuid}/reply",
        data={
            "csrf_token": form_fields(people_client)["csrf_token"],
            "message": "Too late.",
        },
    )

    assert response.status_code == 409


def test_item_is_listed_under_added_to_me(
    people_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
    outside_unit: None,
) -> None:
    item = added_item(people_client, session, models, user)

    added = people_client.get("/moh/feedback/mine?view=added").get_data(as_text=True)
    sent = people_client.get("/moh/feedback/mine").get_data(as_text=True)

    assert item.reference in added
    assert item.reference not in sent


def test_not_for_me_removes_the_person_and_their_access(
    people_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
    outside_unit: None,
) -> None:
    item = added_item(people_client, session, models, user)
    row = item.active_participants[0]
    html = detail(people_client, item).get_data(as_text=True)

    response = people_client.post(
        f"/moh/feedback/{item.uuid}/participants/remove",
        data={
            "csrf_token": _hidden_value(html, "csrf_token"),
            "participant_id": str(row.id),
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/moh/feedback/mine?view=added")
    assert row.removed_on is not None
    assert row.removed_by_fk == 20
    assert history(item)[-1] == "person_removed"
    assert detail(people_client, item).status_code == 404


def remove(client: FlaskClient, item: Any, participant_id: str) -> Any:
    return client.post(
        f"/moh/feedback/{item.uuid}/participants/remove",
        data={
            "csrf_token": form_fields(client)["csrf_token"],
            "participant_id": participant_id,
        },
    )


def test_sender_can_add_and_remove_a_person(
    people_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = sent_to(session, models)
    user.id = 8

    assert (
        add_person(people_client, item, token_of(people_client, "hana.t")).status_code
        == 302
    )
    html = detail(people_client, item).get_data(as_text=True)
    assert "Hana Tesfaye" in html
    assert UNIT.path in html

    assert remove(people_client, item, str(item.participants[0].id)).status_code == 302
    assert item.active_participants == []


def test_added_person_cannot_remove_someone_else(
    people_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
    outside_unit: None,
) -> None:
    item = sent_to(session, models)
    with mock.patch.object(views, "get_user_units", return_value=[UNIT]):
        add_person(people_client, item, token_of(people_client, "hana.t"))
        add_person(people_client, item, token_of(people_client, "no.unit"))
    user.id = 20
    other = item.participants[1]

    assert remove(people_client, item, str(other.id)).status_code == 403
    assert other.removed_on is None


def test_removing_someone_already_removed_is_told(
    people_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)
    add_person(people_client, item, token_of(people_client, "hana.t"))
    row_id = str(item.participants[0].id)
    remove(people_client, item, row_id)

    assert remove(people_client, item, row_id).status_code == 409


def test_person_can_be_added_again_after_removal(
    people_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)
    add_person(people_client, item, token_of(people_client, "hana.t"))
    remove(people_client, item, str(item.participants[0].id))

    assert (
        add_person(people_client, item, token_of(people_client, "hana.t")).status_code
        == 302
    )
    assert len(item.participants) == 2
    assert len(item.active_participants) == 1


def test_same_person_cannot_be_added_twice_to_an_item(
    people_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)
    add_person(people_client, item, token_of(people_client, "hana.t"))

    response = add_person(people_client, item, token_of(people_client, "hana.t"))

    assert response.status_code == 409
    assert len(item.participants) == 1


def test_item_sender_cannot_be_added_to_their_own_item(
    people_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models, owner=20)

    assert (
        add_person(people_client, item, token_of(people_client, "hana.t")).status_code
        == 400
    )


def test_cannot_add_a_person_to_a_closed_item(
    people_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)
    act(people_client, item, "decline", message="Out of scope.")

    assert (
        add_person(people_client, item, token_of(people_client, "hana.t")).status_code
        == 409
    )
    assert 'id="person-search"' not in detail(people_client, item).get_data(
        as_text=True
    )


def test_item_has_a_limit_on_people(
    people_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    people_client.application.config["MOH_FEEDBACK_MAX_PEOPLE_PER_ITEM"] = 1
    item = sent_to(session, models)
    add_person(people_client, item, token_of(people_client, "hana.t"))
    assert 'id="person-search"' not in detail(people_client, item).get_data(
        as_text=True
    )

    response = add_person(people_client, item, token_of(people_client, "no.unit"))

    assert response.status_code == 400
    assert len(item.participants) == 1


def test_earlier_unit_cannot_add_a_person(
    people_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models, is_current=False)

    response = add_person(people_client, item, token_of(people_client, "hana.t"))

    assert response.status_code == 403


def test_stranger_cannot_add_a_person(
    people_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models, unit_id="unit-9")

    response = add_person(people_client, item, token_of(people_client, "hana.t"))

    assert response.status_code == 404


def test_adding_needs_a_valid_form_and_token(
    people_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)
    token = token_of(people_client, "hana.t")

    assert (
        people_client.post(
            f"/moh/feedback/{item.uuid}/participants",
            data={"csrf_token": "x", "person_token": token},
        ).status_code
        == 400
    )
    assert add_person(people_client, item, "forged").status_code == 400
    assert item.participants == []


def test_added_person_does_not_change_who_is_responsible(
    people_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
    outside_unit: None,
) -> None:
    item = added_item(people_client, session, models, user)

    assert item.assigned_to_fk is None
    assert [row.unit_id for row in item.unit_access] == ["unit-1"]
    assert item.reference not in waiting_html(people_client)


def utc(  # noqa: PLR0913
    year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0
) -> datetime:
    return datetime(year, month, day, hour, minute, second)  # noqa: DTZ001


@pytest.mark.parametrize(
    ("start", "days", "expected"),
    [
        # Monday plus five working days is the next Monday
        (utc(2026, 11, 2, 8), 5, utc(2026, 11, 9, 20, 59, 59)),
        # Friday plus one skips the weekend
        (utc(2026, 11, 6, 8), 1, utc(2026, 11, 9, 20, 59, 59)),
        # A weekend start counts from Monday
        (utc(2026, 11, 7, 8), 1, utc(2026, 11, 9, 20, 59, 59)),
        (utc(2026, 11, 8, 8), 5, utc(2026, 11, 13, 20, 59, 59)),
        # 22:00 UTC on Sunday is already Monday in Addis Ababa
        (utc(2026, 11, 8, 22), 1, utc(2026, 11, 10, 20, 59, 59)),
        (utc(2026, 11, 2, 8), 0, utc(2026, 11, 2, 20, 59, 59)),
    ],
)
def test_add_working_days(start: datetime, days: int, expected: datetime) -> None:
    assert deadlines.add_working_days(start, days) == expected


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (utc(2026, 11, 2, 8), utc(2026, 11, 2, 18), 0),
        (utc(2026, 11, 2, 8), utc(2026, 11, 4, 8), 2),
        (utc(2026, 11, 6, 8), utc(2026, 11, 9, 8), 1),
        (utc(2026, 11, 7, 8), utc(2026, 11, 8, 8), 0),
        (utc(2026, 11, 2, 8), utc(2026, 11, 16, 8), 10),
    ],
)
def test_working_days_between(start: datetime, end: datetime, expected: int) -> None:
    assert deadlines.working_days_between(start, end) == expected


def timed(**values: Any) -> SimpleNamespace:
    defaults = {
        "status": "new",
        "first_response_on": None,
        "first_response_due_on": utc(2026, 11, 10),
        "due_on": utc(2026, 11, 20),
    }
    return SimpleNamespace(**{**defaults, **values})


@pytest.mark.parametrize(
    ("values", "now", "expected"),
    [
        ({}, utc(2026, 11, 9), False),
        ({}, utc(2026, 11, 11), True),
        ({"first_response_on": utc(2026, 11, 9)}, utc(2026, 11, 11), False),
        ({"first_response_on": utc(2026, 11, 9)}, utc(2026, 11, 21), True),
        ({"status": "needs_info"}, utc(2026, 11, 21), False),
        ({"status": "answered"}, utc(2026, 11, 21), False),
        ({"status": "closed"}, utc(2026, 11, 21), False),
        ({"status": "assigned"}, utc(2026, 11, 21), True),
        (
            {"due_on": None, "first_response_on": utc(2026, 11, 9)},
            utc(2030, 1, 1),
            False,
        ),
    ],
)
def test_is_overdue(values: dict[str, Any], now: datetime, expected: bool) -> None:
    assert is_overdue(timed(**values), now) is expected


def started_item(session: Session, models: tuple[Any, Any], **values: Any) -> Any:
    item = sent_to(session, models)
    item.clock_started_on = utc(2026, 11, 2, 8)
    item.paused_days = 0
    for name, value in values.items():
        setattr(item, name, value)
    session.commit()
    return item


def test_new_feedback_starts_as_normal_with_deadlines(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    send_with(client, [])

    item = session.query(models[0]).one()
    assert item.priority == "normal"
    assert item.first_response_due_on == deadlines.add_working_days(item.created_on, 5)
    assert item.due_on == deadlines.add_working_days(item.created_on, 14)
    assert item.paused_days == 0


@pytest.mark.parametrize(
    ("priority", "first_days", "due_days"),
    [("high", 2, 5), ("normal", 5, 14), ("low", 5, None)],
)
def test_priority_sets_the_deadlines(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    priority: str,
    first_days: int,
    due_days: int | None,
) -> None:
    item = started_item(session, models)

    response = act(handled_client, item, "set_priority", priority=priority)

    assert response.status_code == 302
    start = item.clock_started_on
    assert item.priority == priority
    assert item.first_response_due_on == deadlines.add_working_days(start, first_days)
    assert item.due_on == (
        deadlines.add_working_days(start, due_days) if due_days else None
    )
    assert (history(item)[-1], item.events[-1].message) == (
        "priority_changed",
        priority.capitalize(),
    )
    assert item.status == "new"


def test_deadlines_can_be_changed_in_settings(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    handled_client.application.config["MOH_FEEDBACK_DEADLINES"] = {
        "high": (1, 1),
        "normal": (1, 2),
        "low": (1, 3),
    }
    item = started_item(session, models)

    act(handled_client, item, "set_priority", priority="low")

    assert item.due_on == deadlines.add_working_days(item.clock_started_on, 3)


@pytest.mark.parametrize("priority", ["urgent", "", "HIGH"])
def test_unknown_priority_is_refused(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    priority: str,
) -> None:
    item = started_item(session, models)

    assert (
        act(handled_client, item, "set_priority", priority=priority).status_code == 400
    )
    assert item.priority == "normal"


def test_sender_cannot_set_the_priority(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = started_item(session, models)
    user.id = 8

    response = handled_client.post(
        f"/moh/feedback/{item.uuid}/action",
        data={
            "csrf_token": form_fields(handled_client)["csrf_token"],
            "expected_status": "new",
            "action": "set_priority",
            "priority": "high",
        },
    )

    assert response.status_code == 403
    assert item.priority == "normal"


def test_priority_cannot_change_once_answered(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = started_item(session, models)
    act(handled_client, item, "answer", message="Done.")

    html = detail(handled_client, item).get_data(as_text=True)

    assert 'value="set_priority"' not in html
    response = handled_client.post(
        f"/moh/feedback/{item.uuid}/action",
        data={
            "csrf_token": _hidden_value(html, "csrf_token"),
            "expected_status": "answered",
            "action": "set_priority",
            "priority": "high",
        },
    )
    assert response.status_code == 409


def test_waiting_for_the_sender_moves_the_deadline_back(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = started_item(session, models)
    act(handled_client, item, "set_priority", priority="normal")
    original_due = item.due_on
    act(handled_client, item, "ask", message="Which month?")
    assert item.paused_on is not None
    now = datetime.utcnow()
    item.paused_on = now - timedelta(days=7)
    session.commit()
    expected = deadlines.working_days_between(item.paused_on, now)
    user.id = 8

    reply(handled_client, item, "Meskerem.")

    assert item.paused_on is None
    assert item.paused_days == expected
    assert item.due_on == deadlines.add_working_days(
        item.clock_started_on, 14 + expected
    )
    assert item.due_on > original_due


def reply(client: FlaskClient, item: Any, message: str) -> Any:
    html = detail(client, item).get_data(as_text=True)
    return client.post(
        f"/moh/feedback/{item.uuid}/reply",
        data={"csrf_token": _hidden_value(html, "csrf_token"), "message": message},
    )


def test_replying_the_same_day_keeps_the_deadline(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = started_item(session, models)
    act(handled_client, item, "set_priority", priority="normal")
    original_due = item.due_on
    act(handled_client, item, "ask", message="Which month?")
    user.id = 8

    reply(handled_client, item, "Meskerem.")

    assert item.due_on == original_due


def test_deadline_also_moves_back_while_waiting_for_confirmation(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = started_item(session, models)
    act(handled_client, item, "set_priority", priority="normal")
    original_due = item.due_on
    act(handled_client, item, "answer", message="Done.")
    item.paused_on = datetime.utcnow() - timedelta(days=7)
    session.commit()
    user.id = 8

    decide(handled_client, item, "not_solved", "Still wrong.")

    assert item.paused_on is None
    assert item.due_on > original_due


def test_changing_priority_keeps_paused_days(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = started_item(session, models, paused_days=3)

    act(handled_client, item, "set_priority", priority="high")

    assert item.due_on == deadlines.add_working_days(item.clock_started_on, 8)


def test_overdue_items_are_marked_and_come_first(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    later = started_item(
        session,
        models,
        message="Item with a later date",
        due_on=datetime.utcnow() + timedelta(days=9),
        first_response_due_on=datetime.utcnow() + timedelta(days=3),
    )
    late = started_item(
        session,
        models,
        message="Item past its date",
        due_on=datetime.utcnow() - timedelta(days=1),
        first_response_due_on=datetime.utcnow() - timedelta(days=3),
    )
    started_item(session, models, message="Item without any date", priority="low")

    html = waiting_html(handled_client)

    assert (
        html.index("Item past its date")
        < html.index("Item with a later date")
        < html.index("Item without any date")
    )
    assert html.count('class="status overdue"') == 1
    assert 'class="status overdue"' in detail(handled_client, late).get_data(
        as_text=True
    )
    assert 'class="status overdue"' not in detail(handled_client, later).get_data(
        as_text=True
    )


def test_page_shows_the_deadlines(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = started_item(
        session,
        models,
        first_response_due_on=utc(2026, 11, 9, 20, 59, 59),
        due_on=utc(2026, 11, 20, 20, 59, 59),
    )

    html = detail(handled_client, item).get_data(as_text=True)

    assert "First response by" in html
    assert "9 Nov 2026" in html
    assert "20 Nov 2026" in html


def test_item_without_deadlines_still_displays(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)

    assert "Finish by" not in detail(handled_client, item).get_data(as_text=True)


CHILD_UNIT = OrgUnit(
    "child",
    "Child Facility",
    "Federal › Sample Region › Sample Woreda › Child Facility",
    ("root", "region", "unit-1", "child", None, None, None),
    False,
    level=4,
    leaf=True,
)
KNOWN_UNITS = {unit.id: unit for unit in (UNIT, PARENT_UNIT, CHILD_UNIT, CLOSED_UNIT)}


@pytest.fixture
def move_client(handled_client: FlaskClient) -> Iterator[FlaskClient]:
    with (
        mock.patch.object(
            views,
            "get_units",
            side_effect=lambda ids: {
                i: KNOWN_UNITS[i] for i in ids if i in KNOWN_UNITS
            },
        ),
        mock.patch.object(views, "_item_sender_username", return_value="the.sender"),
        mock.patch.object(views, "find_destination_down", return_value=CHILD_UNIT),
    ):
        yield handled_client


def move(client: FlaskClient, item: Any, **values: str) -> Any:
    data = {
        "csrf_token": form_fields(client)["csrf_token"],
        "expected_status": item.status,
        "reason": "Not for our unit.",
        **values,
    }
    return client.post(f"/moh/feedback/{item.uuid}/move", data=data)


def current_units(item: Any) -> list[str]:
    return [row.unit_id for row in item.unit_access if row.is_current]


def test_handler_can_send_an_item_up(
    move_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = started_item(session, models)
    act(move_client, item, "assign", assignee_id="9")

    assert move(move_client, item, direction="up").status_code == 302

    assert item.status == "new"
    assert item.assigned_to_fk is None
    assert item.assignee_name is None
    assert item.first_response_on is None
    assert current_units(item) == [PARENT_UNIT.id]
    assert (item.target_unit_id, item.target_unit_name, item.target_path) == (
        PARENT_UNIT.id,
        PARENT_UNIT.name,
        PARENT_UNIT.path,
    )
    moved = next(event for event in item.events if event.event_type == "moved")
    assert (moved.from_unit_id, moved.to_unit_id, moved.message) == (
        "unit-1",
        PARENT_UNIT.id,
        "Not for our unit.",
    )
    assert history(item)[-1] == "routed"


def test_moving_restarts_the_clock(
    move_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = started_item(session, models, paused_days=4)
    old_due = item.due_on

    move(move_client, item, direction="up")

    assert item.clock_started_on > utc(2026, 11, 3)
    assert item.paused_days == 0
    assert item.paused_on is None
    assert item.due_on != old_due
    assert not is_overdue(item, datetime.utcnow())


def test_previous_unit_can_read_but_no_longer_act(
    move_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = started_item(session, models)
    move(move_client, item, direction="up")

    html = detail(move_client, item).get_data(as_text=True)

    assert "Not for our unit." in html
    assert 'value="answer"' not in html
    assert 'id="move-form"' not in html
    assert (
        move_client.post(
            f"/moh/feedback/{item.uuid}/action", data={"action": "note"}
        ).status_code
        == 403
    )
    assert move_client.post(f"/moh/feedback/{item.uuid}/move").status_code == 403
    assert MESSAGE not in waiting_html(move_client)


def test_new_unit_receives_the_item_and_can_act(
    move_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = started_item(session, models)
    move(move_client, item, direction="up")
    user.id = 30

    with mock.patch.object(views, "get_user_units", return_value=[PARENT_UNIT]):
        assert MESSAGE in waiting_html(move_client)
        assert 'value="answer"' in detail(move_client, item).get_data(as_text=True)


def test_sender_sees_where_it_went_and_why(
    move_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = started_item(session, models)
    move(move_client, item, direction="up")
    user.id = 8

    html = detail(move_client, item).get_data(as_text=True)

    assert "Not for our unit." in html
    assert PARENT_UNIT.name in html
    assert 'id="move-form"' not in html


def test_handler_can_move_an_item_down(
    move_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = started_item(session, models)

    response = move(move_client, item, direction="down", target_unit_id="child")

    assert response.status_code == 302
    assert current_units(item) == ["child"]


def test_item_can_return_to_a_unit_it_was_at(
    move_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = started_item(session, models)
    move(move_client, item, direction="up")
    user.id = 30
    with (
        mock.patch.object(views, "get_user_units", return_value=[PARENT_UNIT]),
        mock.patch.object(views, "find_destination_down", return_value=UNIT),
    ):
        response = move(move_client, item, direction="down", target_unit_id="unit-1")

    assert response.status_code == 302
    assert current_units(item) == ["unit-1"]
    assert len(item.unit_access) == 3


@pytest.mark.parametrize(
    ("target", "message"),
    [
        ("", "Choose a unit below yours."),
        ("missing", "Choose a unit below yours."),
        ("unit-3", "Choose a unit below yours."),
        ("unit-1", "Choose a unit below yours."),
        (PARENT_UNIT.id, "Choose a unit below yours."),
    ],
)
def test_cannot_move_down_to_an_invalid_unit(
    move_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    target: str,
    message: str,
) -> None:
    item = started_item(session, models)

    response = move(move_client, item, direction="down", target_unit_id=target)

    assert response.status_code == 400
    assert message in response.get_data(as_text=True)
    assert current_units(item) == ["unit-1"]


def test_cannot_move_down_when_nobody_can_receive_it(
    move_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = started_item(session, models)

    with mock.patch.object(views, "find_destination_down", return_value=None):
        response = move(move_client, item, direction="down", target_unit_id="child")

    assert response.status_code == 400
    assert current_units(item) == ["unit-1"]


@pytest.mark.parametrize("destination", [None, UNIT])
def test_cannot_send_up_when_there_is_no_level_above(
    move_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    destination: OrgUnit | None,
) -> None:
    item = started_item(session, models)

    with mock.patch.object(views, "find_destination_up", return_value=destination):
        html = detail(move_client, item).get_data(as_text=True)
        response = move(move_client, item, direction="up")

    assert 'value="up"' not in html
    assert "There is no level above" in html
    assert response.status_code == 400
    assert current_units(item) == ["unit-1"]


@pytest.mark.parametrize(
    ("values", "reason"),
    [
        ({"direction": "up", "reason": ""}, "blank"),
        ({"direction": "up", "reason": "  \r\n "}, "spaces"),
        ({"direction": "up", "reason": "x" * 2001}, "long"),
        ({"direction": "sideways"}, "direction"),
        ({"direction": ""}, "no direction"),
    ],
)
def test_move_needs_valid_input(
    move_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    values: dict[str, str],
    reason: str,
) -> None:
    item = started_item(session, models)

    assert move(move_client, item, **values).status_code == 400, reason
    assert current_units(item) == ["unit-1"]


def test_move_refused_while_org_units_are_unavailable(
    move_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = started_item(session, models)

    with mock.patch.object(views, "get_units", side_effect=OrgUnitLookupError("x")):
        html = detail(move_client, item).get_data(as_text=True)
        response = move(move_client, item, direction="up")

    assert response.status_code == 503
    assert 'value="up"' not in html
    assert current_units(item) == ["unit-1"]


def test_move_refused_from_a_stale_page(
    move_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = started_item(session, models)

    response = move(move_client, item, direction="up", expected_status="assigned")

    assert response.status_code == 409
    assert current_units(item) == ["unit-1"]


def test_move_refused_on_a_forged_form(
    move_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = started_item(session, models)

    assert (
        move(move_client, item, direction="up", csrf_token="forged").status_code == 400  # noqa: S106
    )


@pytest.mark.parametrize("action", ["answer", "decline"])
def test_cannot_move_a_finished_item(
    move_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    action: str,
) -> None:
    item = started_item(session, models)
    act(move_client, item, action, message="Finished.")
    status = item.status

    html = detail(move_client, item).get_data(as_text=True)
    response = move(move_client, item, direction="up", expected_status=status)

    assert 'id="move-form"' not in html
    assert response.status_code == 409
    assert current_units(item) == ["unit-1"]


def test_item_waiting_on_the_sender_can_be_moved(
    move_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = started_item(session, models)
    act(move_client, item, "ask", message="Which month?")

    response = move(move_client, item, direction="up", expected_status="needs_info")

    assert response.status_code == 302
    assert item.status == "new"
    assert item.paused_on is None


def test_sender_cannot_move_their_item(
    move_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = started_item(session, models)
    user.id = 8

    response = move_client.post(
        f"/moh/feedback/{item.uuid}/move", data={"direction": "up", "reason": "x"}
    )

    assert response.status_code == 403
    assert 'id="move-form"' not in detail(move_client, item).get_data(as_text=True)


def test_added_person_cannot_move_the_item(
    move_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = started_item(session, models)
    participant = models[0].participants.property.mapper.class_
    item.participants.append(participant(user_id=20, display_name="Someone"))
    session.commit()
    user.id = 20

    with mock.patch.object(views, "get_user_units", return_value=[OTHER_UNIT]):
        response = move_client.post(
            f"/moh/feedback/{item.uuid}/move", data={"direction": "up", "reason": "x"}
        )

    assert response.status_code == 403


def test_stranger_cannot_move_the_item(
    move_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models, unit_id="unit-9")

    response = move_client.post(f"/moh/feedback/{item.uuid}/move", data={})

    assert response.status_code == 404


def test_move_needs_a_sign_in(
    move_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = started_item(session, models)
    user.is_authenticated = False

    response = move_client.post(f"/moh/feedback/{item.uuid}/move", data={})

    assert response.status_code == 302
    assert response.headers["Location"] == "/login/"


def test_move_is_hidden_when_the_feature_is_off(
    move_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = started_item(session, models)
    move_client.application.config["MOH_FEEDBACK_ENABLED"] = False

    assert move_client.post(f"/moh/feedback/{item.uuid}/move").status_code == 404


def test_leaf_unit_is_not_offered_moving_down(
    move_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = started_item(session, models)
    leaf = OrgUnit("unit-1", "Leaf", "Leaf", (None,) * 7, False, leaf=True)

    with mock.patch.object(views, "get_units", return_value={"unit-1": leaf}):
        html = detail(move_client, item).get_data(as_text=True)

    assert 'id="move-search"' not in html
    assert 'value="up"' in html


def test_acting_after_the_item_moved_away_is_refused(
    move_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = started_item(session, models)
    real_lock = views._lock_item

    def move_while_waiting(db: Any, item_id: int) -> Any:
        locked = real_lock(db, item_id)
        locked.unit_access[0].unit_id = PARENT_UNIT.id
        return locked

    with mock.patch.object(views, "_lock_item", side_effect=move_while_waiting):
        response = act(move_client, item, "answer", message="Too late.")

    assert response.status_code == 409
    assert item.status == "new"


@pytest.fixture
def sent_mail() -> Iterator[mock.MagicMock]:
    with (
        mock.patch.object(notifications, "_send_email") as send,
        mock.patch.object(
            notifications,
            "_recipient_email",
            side_effect=lambda user_id, _: f"user{user_id}@mail.test",
        ),
        mock.patch("superset.moh_alerts.tasks._paused_addresses", return_value=set()),
    ):
        yield send


@pytest.fixture
def mail_client(
    move_client: FlaskClient, sent_mail: mock.MagicMock
) -> Iterator[FlaskClient]:
    move_client.application.config["MOH_FEEDBACK_EMAILS_ENABLED"] = True
    move_client.application.config["MOH_ALERTS_WEB_HOST"] = "https://portal.test/"
    with move_client.application.app_context():
        yield move_client


def queued(session: Session) -> list[Any]:
    model = _notification_model()
    return session.query(model).order_by(model.id).all()


def _notification_model() -> Any:
    from superset.models.moh_feedback import MohFeedbackNotification

    return MohFeedbackNotification


def jobs_db(session: Session) -> SimpleNamespace:
    return SimpleNamespace(session=session)


def add_mail(session: Session, item: Any, **values: Any) -> Any:
    fields = {
        "user_id": 8,
        "kind": "answered",
        "status": "pending",
        "next_attempt_on": datetime.utcnow() - timedelta(minutes=1),
        **values,
    }
    row = _notification_model()(feedback_id=item.id if item else None, **fields)
    session.add(row)
    session.commit()
    return row


def test_nothing_is_queued_while_emails_are_off(
    move_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = started_item(session, models)

    act(move_client, item, "answer", message="Done.")

    assert queued(session) == []


def test_sender_is_told_their_feedback_was_received(
    mail_client: FlaskClient, session: Session
) -> None:
    send_with(mail_client, [])

    assert [(row.kind, row.user_id) for row in queued(session)] == [("received", 7)]


@pytest.mark.parametrize(
    ("action", "kind"),
    [("ask", "asked"), ("answer", "answered"), ("decline", "declined")],
)
def test_sender_is_told_about_a_response(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    action: str,
    kind: str,
) -> None:
    item = started_item(session, models)

    act(mail_client, item, action, message="A response.")

    rows = queued(session)
    assert [(row.kind, row.user_id, row.actor_name) for row in rows] == [
        (kind, 8, "Sample User")
    ]


def test_assignee_is_told_but_not_when_assigning_yourself(
    mail_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = started_item(session, models)

    act(mail_client, item, "assign", assignee_id="7")
    assert queued(session) == []

    act(mail_client, item, "assign", assignee_id="9")
    assert [(row.kind, row.user_id) for row in queued(session)] == [("assigned", 9)]


@pytest.mark.parametrize(
    ("action", "extra"),
    [
        ("start_review", {}),
        ("note", {"message": "Private."}),
        ("set_priority", {"priority": "high"}),
    ],
)
def test_quiet_actions_send_no_email(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    action: str,
    extra: dict[str, str],
) -> None:
    item = started_item(session, models)

    act(mail_client, item, action, **extra)

    assert queued(session) == []


def test_added_person_is_told_once(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
) -> None:
    item = started_item(session, models)
    with (
        mock.patch.object(people, "active_accounts", return_value=[HANA]),
        mock.patch.object(
            people, "get_user_units", side_effect=PERSON_UNITS.__getitem__
        ),
        mock.patch.object(views, "active_user_ids", return_value={20}),
    ):
        add_person(mail_client, item, token_of(mail_client, "hana.t"))

    assert [(row.kind, row.user_id) for row in queued(session)] == [("added", 20)]


def test_reply_goes_to_the_unit_when_nobody_is_assigned(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = started_item(session, models)
    act(mail_client, item, "ask", message="Which month?")
    user.id = 8

    reply(mail_client, item, "Meskerem.")

    row = queued(session)[-1]
    assert (row.kind, row.user_id, row.unit_id) == ("replied", None, "unit-1")


def test_not_solved_goes_to_the_assignee(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = started_item(session, models)
    act(mail_client, item, "assign", assignee_id="9")
    act(mail_client, item, "answer", message="Done.")
    user.id = 8

    decide(mail_client, item, "not_solved", "Still wrong.")

    row = queued(session)[-1]
    assert (row.kind, row.user_id, row.unit_id) == ("not_solved", 9, None)


def test_solved_sends_no_email(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = started_item(session, models)
    act(mail_client, item, "answer", message="Done.")
    before = len(queued(session))
    user.id = 8

    decide(mail_client, item, "solved")

    assert len(queued(session)) == before


def test_move_tells_sender_old_assignee_and_new_unit(
    mail_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = started_item(session, models)
    act(mail_client, item, "assign", assignee_id="9")

    move(mail_client, item, direction="up")

    assert {(row.kind, row.user_id, row.unit_id) for row in queued(session)[1:]} == {
        ("moved_sender", 8, None),
        ("moved_assignee", 9, None),
        ("moved_unit", None, PARENT_UNIT.id),
    }


@pytest.mark.parametrize("kind", sorted(notifications._TEMPLATES))
def test_every_email_has_a_link_and_no_conversation(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    kind: str,
) -> None:
    item = started_item(session, models, message="A private message about a clinic.")
    row = add_mail(session, item, kind=kind, actor_name="Sample User")

    subject, body = notifications.render(row)

    assert subject.startswith(f"[{item.reference}] ")
    assert f"https://portal.test/moh/feedback/{item.uuid}" in body
    assert "A private message" not in body
    assert "Sample User" not in subject


def test_email_escapes_names(
    mail_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = started_item(session, models)
    row = add_mail(
        session, item, kind="assigned", actor_name="<script>alert(1)</script>"
    )

    assert "<script>" not in notifications.render(row)[1]


def test_queued_email_is_sent_once(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    sent_mail: mock.MagicMock,
) -> None:
    item = started_item(session, models)
    row = add_mail(session, item)

    notifications.deliver_due(jobs_db(session))
    notifications.deliver_due(jobs_db(session))

    assert sent_mail.call_count == 1
    assert sent_mail.call_args.args[0] == "user8@mail.test"
    assert row.status == "sent"
    assert row.sent_on is not None


def test_only_the_pilot_list_receives_email(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    sent_mail: mock.MagicMock,
) -> None:
    mail_client.application.config["MOH_FEEDBACK_EMAIL_ONLY_TO"] = ["USER9@mail.test"]
    item = started_item(session, models)
    skipped = add_mail(session, item, user_id=8)
    allowed = add_mail(session, item, user_id=9)

    notifications.deliver_due(jobs_db(session))

    assert sent_mail.call_count == 1
    assert (skipped.status, skipped.error_message) == (
        "skipped",
        "Not on the pilot list.",
    )
    assert allowed.status == "sent"


@pytest.mark.parametrize(
    "address",
    [None, "someone@example.org"],
)
def test_unusable_addresses_are_skipped(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    sent_mail: mock.MagicMock,
    address: str | None,
) -> None:
    item = started_item(session, models)
    row = add_mail(session, item)

    with mock.patch.object(notifications, "_recipient_email", return_value=address):
        notifications.deliver_due(jobs_db(session))

    assert row.status == "skipped"
    sent_mail.assert_not_called()


def test_recently_rejected_address_is_skipped(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    sent_mail: mock.MagicMock,
) -> None:
    item = started_item(session, models)
    row = add_mail(session, item)

    with mock.patch(
        "superset.moh_alerts.tasks._paused_addresses",
        return_value={"user8@mail.test"},
    ):
        notifications.deliver_due(jobs_db(session))

    assert row.status == "skipped"
    sent_mail.assert_not_called()


def test_temporary_failure_is_retried_later(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    sent_mail: mock.MagicMock,
) -> None:
    item = started_item(session, models)
    row = add_mail(session, item)
    sent_mail.side_effect = smtplib.SMTPResponseException(451, b"Try later")
    now = datetime.utcnow()

    notifications.deliver_due(jobs_db(session), now)
    assert (row.status, row.attempts) == ("pending", 1)
    assert row.next_attempt_on == now + timedelta(minutes=5)

    notifications.deliver_due(jobs_db(session), now)
    assert sent_mail.call_count == 1

    sent_mail.side_effect = None
    notifications.deliver_due(jobs_db(session), now + timedelta(minutes=6))
    assert row.status == "sent"


def test_gives_up_after_repeated_failures(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    sent_mail: mock.MagicMock,
) -> None:
    item = started_item(session, models)
    row = add_mail(session, item)
    sent_mail.side_effect = ConnectionRefusedError()

    for day in range(1, 7):
        notifications.deliver_due(
            jobs_db(session), datetime.utcnow() + timedelta(days=day)
        )

    assert row.status == "failed"
    assert row.attempts == 5


def test_invalid_address_is_not_retried(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    sent_mail: mock.MagicMock,
) -> None:
    item = started_item(session, models)
    row = add_mail(session, item)
    sent_mail.side_effect = smtplib.SMTPRecipientsRefused(
        {"user8@mail.test": (550, b"No such user")}
    )

    notifications.deliver_due(jobs_db(session))

    assert (row.status, row.attempts) == ("failed", 1)


def test_sending_pauses_when_the_provider_is_refusing(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    sent_mail: mock.MagicMock,
) -> None:
    item = started_item(session, models)
    for _ in range(5):
        add_mail(session, item)
    sent_mail.side_effect = smtplib.SMTPResponseException(451, b"Try later")

    notifications.deliver_due(jobs_db(session))

    assert sent_mail.call_count == 3


def test_batch_size_is_respected(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    sent_mail: mock.MagicMock,
) -> None:
    mail_client.application.config["MOH_FEEDBACK_NOTIFICATION_BATCH"] = 2
    item = started_item(session, models)
    for _ in range(5):
        add_mail(session, item)

    notifications.deliver_due(jobs_db(session))

    assert sent_mail.call_count == 2


def test_unit_email_goes_to_each_handler_except_the_actor_and_sender(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    sent_mail: mock.MagicMock,
) -> None:
    item = started_item(session, models)
    parent = add_mail(session, item, user_id=None, unit_id="unit-1", exclude_user_id=9)
    people_found = [Person(7, "A"), Person(9, "B")]

    with mock.patch(
        "superset.moh_feedback.routing.unit_handlers", return_value=people_found
    ) as handlers:
        notifications.deliver_due(jobs_db(session))

    handlers.assert_called_once_with("unit-1", item.created_by_fk)
    assert parent.status == "expanded"
    assert [args.args[0] for args in sent_mail.call_args_list] == ["user7@mail.test"]


def test_unit_email_waits_while_org_units_are_unavailable(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    sent_mail: mock.MagicMock,
) -> None:
    item = started_item(session, models)
    row = add_mail(session, item, user_id=None, unit_id="unit-1")

    with mock.patch(
        "superset.moh_feedback.routing.unit_handlers",
        side_effect=OrgUnitLookupError("x"),
    ):
        notifications.deliver_due(jobs_db(session))

    assert row.status == "pending"
    assert row.next_attempt_on > datetime.utcnow()
    sent_mail.assert_not_called()


def test_digest_is_one_summary_per_person_once_a_day(
    mail_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    started_item(session, models)
    started_item(
        session,
        models,
        status="assigned",
        due_on=datetime.utcnow() - timedelta(days=1),
    )
    started_item(session, models, status="in_review")

    with mock.patch.object(
        tasks, "unit_handlers", return_value=[Person(7, "A"), Person(8, "The sender")]
    ):
        tasks.queue_daily_digest(jobs_db(session))
        tasks.queue_daily_digest(jobs_db(session))

    rows = queued(session)
    # Person 8 sent all three items, so has nothing waiting
    assert [row.user_id for row in rows] == [7]
    assert json.loads(rows[0].detail) == {"new": 1, "overdue": 1}
    subject, body = notifications.render(rows[0])
    assert subject == "Your feedback summary"
    assert "1 new and 1 overdue" in body


def test_no_digest_when_nothing_is_waiting(
    mail_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    started_item(session, models, status="in_review")

    with mock.patch.object(tasks, "unit_handlers", return_value=[Person(7, "A")]):
        tasks.queue_daily_digest(jobs_db(session))

    assert queued(session) == []


@pytest.mark.parametrize("status", ["answered", "needs_info"])
def test_item_closes_after_waiting_on_the_sender(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    status: str,
) -> None:
    item = started_item(
        session,
        models,
        status=status,
        paused_on=datetime.utcnow() - timedelta(days=15),
    )

    assert tasks.auto_close_items(jobs_db(session)) == 1

    assert (item.status, item.closure_reason) == ("closed", "no_response")
    assert item.closed_on is not None
    assert history(item)[-1] == "auto_closed"
    assert [(row.kind, row.user_id) for row in queued(session)] == [("auto_closed", 8)]
    assert "Closed (no response)" in detail(mail_client, item).get_data(as_text=True)


def test_item_stays_open_before_the_waiting_period_ends(
    mail_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = started_item(
        session,
        models,
        status="answered",
        paused_on=datetime.utcnow() - timedelta(days=13),
    )

    assert tasks.auto_close_items(jobs_db(session)) == 0
    assert item.status == "answered"


def test_handled_items_are_not_closed_automatically(
    mail_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = started_item(
        session,
        models,
        status="in_review",
        paused_on=datetime.utcnow() - timedelta(days=30),
    )

    assert tasks.auto_close_items(jobs_db(session)) == 0
    assert item.status == "in_review"


def overdue_item(session: Session, models: tuple[Any, Any], **values: Any) -> Any:
    return started_item(
        session,
        models,
        due_on=datetime.utcnow() - timedelta(days=1),
        first_response_due_on=datetime.utcnow() - timedelta(days=3),
        **values,
    )


@pytest.fixture
def escalation() -> Iterator[mock.MagicMock]:
    with (
        mock.patch.object(tasks, "sender_username", return_value="the.sender"),
        mock.patch.object(
            tasks,
            "get_units",
            side_effect=lambda ids: {
                i: KNOWN_UNITS[i] for i in ids if i in KNOWN_UNITS
            },
        ),
        mock.patch.object(
            tasks, "find_escalation_target", return_value=PARENT_UNIT
        ) as target,
    ):
        yield target


def test_overdue_item_moves_up_automatically(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    escalation: mock.MagicMock,
) -> None:
    item = overdue_item(session, models, status="assigned", assigned_to_fk=9)

    assert tasks.escalate_overdue_items(jobs_db(session)) == 1

    assert item.status == "new"
    assert item.assigned_to_fk is None
    assert current_units(item) == [PARENT_UNIT.id]
    moved = next(event for event in item.events if event.event_type == "moved")
    assert (moved.user_id, moved.actor_name) == (None, "System")
    assert item.unit_access[-1].reason == "escalated"
    assert not is_overdue(item, datetime.utcnow())
    assert tasks.escalate_overdue_items(jobs_db(session)) == 0
    assert {row.kind for row in queued(session)} == {
        "moved_sender",
        "moved_assignee",
        "moved_unit",
    }


def test_overdue_item_stays_when_there_is_nowhere_to_go(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    escalation: mock.MagicMock,
) -> None:
    item = overdue_item(session, models)
    escalation.return_value = None

    assert tasks.escalate_overdue_items(jobs_db(session)) == 0
    assert current_units(item) == ["unit-1"]


def test_items_on_time_or_waiting_on_the_sender_do_not_move(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    escalation: mock.MagicMock,
) -> None:
    started_item(session, models, due_on=datetime.utcnow() + timedelta(days=2))
    overdue_item(session, models, status="needs_info")
    overdue_item(session, models, status="answered")

    assert tasks.escalate_overdue_items(jobs_db(session)) == 0


def test_escalation_stops_cleanly_when_org_units_are_unavailable(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    escalation: mock.MagicMock,
) -> None:
    item = overdue_item(session, models)
    escalation.side_effect = OrgUnitLookupError("x")

    assert tasks.escalate_overdue_items(jobs_db(session)) == 0
    assert current_units(item) == ["unit-1"]


@pytest.mark.parametrize(
    ("direction", "origin", "expected"),
    [
        ("up", "unit-1", [PARENT_UNIT.id, "root"]),
        ("down", "root", [PARENT_UNIT.id]),
        ("down", PARENT_UNIT.id, []),
        ("down", None, [PARENT_UNIT.id, "root"]),
    ],
)
def test_escalation_path_stops_below_a_downward_sender(
    direction: str, origin: str | None, expected: list[str]
) -> None:
    with (
        mock.patch.object(routing, "get_units", return_value={}) as get_units,
        mock.patch.object(routing, "count_handlers", return_value={}),
    ):
        routing.find_escalation_target(UNIT, "someone", direction, origin)

    assert get_units.call_args.args[0] == tuple(expected)


def pending_item(session: Session, models: tuple[Any, Any]) -> Any:
    return add_item(session, models, 8, MESSAGE)


def test_pending_item_is_routed_when_units_return(
    mail_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = pending_item(session, models)
    session.commit()

    with (
        mock.patch.object(tasks, "sender_username", return_value="the.sender"),
        mock.patch.object(tasks, "get_user_units", return_value=[UNIT]),
        mock.patch.object(tasks, "find_destination_up", return_value=PARENT_UNIT),
    ):
        assert tasks.route_pending_items(jobs_db(session)) == 1

    assert item.origin_unit_id == UNIT.id
    assert item.target_unit_id == PARENT_UNIT.id
    assert current_units(item) == [PARENT_UNIT.id]
    assert history(item)[-1] == "routed"


def test_pending_item_waits_while_units_are_unavailable(
    mail_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = pending_item(session, models)
    session.commit()

    with (
        mock.patch.object(tasks, "sender_username", return_value="the.sender"),
        mock.patch.object(tasks, "get_user_units", return_value=None),
    ):
        assert tasks.route_pending_items(jobs_db(session)) == 0

    assert item.target_unit_id is None


@pytest.mark.parametrize(
    ("job", "worker", "setting"),
    [
        (tasks.send_notifications, "deliver_due", "MOH_FEEDBACK_EMAILS_ENABLED"),
        (tasks.daily_digest, "queue_daily_digest", "MOH_FEEDBACK_EMAILS_ENABLED"),
        (tasks.auto_close, "auto_close_items", "MOH_FEEDBACK_AUTOMATION_ENABLED"),
        (tasks.escalate, "escalate_overdue_items", "MOH_FEEDBACK_AUTOMATION_ENABLED"),
        (
            tasks.route_pending,
            "route_pending_items",
            "MOH_FEEDBACK_AUTOMATION_ENABLED",
        ),
    ],
)
def test_jobs_do_nothing_until_switched_on(job: Any, worker: str, setting: str) -> None:
    app = Flask(__name__)
    with app.app_context(), mock.patch.object(tasks, worker) as run:
        job.run()
        run.assert_not_called()
        app.config[setting] = True
        with mock.patch.object(tasks, "_load_db"):
            job.run()
        run.assert_called_once()


def image_bytes(
    image_format: str = "PNG",
    size: tuple[int, int] = (40, 30),
    mode: str = "RGB",
    **options: Any,
) -> bytes:
    output = io.BytesIO()
    Image.new(mode, size, 120).save(output, image_format, **options)
    return output.getvalue()


def upload(data: bytes, name: str = "screen.png") -> SimpleNamespace:
    stream = io.BytesIO(data)
    return SimpleNamespace(read=stream.read, filename=name)


@pytest.fixture
def uploads(client: FlaskClient, tmp_path: Path) -> Iterator[Path]:
    folder = tmp_path / "uploads"
    client.application.config["MOH_FEEDBACK_UPLOAD_DIR"] = str(folder)
    with client.application.app_context():
        yield folder


def test_screenshot_keeps_the_picture(uploads: Path) -> None:
    clean = attachments.clean_screenshot(upload(image_bytes(size=(64, 48))))

    with Image.open(io.BytesIO(clean.data)) as image:
        assert (image.format, image.size) == ("PNG", (64, 48))
    assert (clean.extension, clean.content_type) == ("png", "image/png")


def test_png_hidden_text_is_removed(uploads: Path) -> None:
    info = PngImagePlugin.PngInfo()
    info.add_text("Author", "SECRET-PERSON")

    clean = attachments.clean_screenshot(upload(image_bytes(pnginfo=info)))

    assert b"SECRET-PERSON" not in clean.data


def test_photo_location_and_camera_data_are_removed(uploads: Path) -> None:
    exif = Image.Exif()
    exif[0x010F] = "SECRET-CAMERA"
    raw = image_bytes("JPEG", exif=exif)
    assert b"SECRET-CAMERA" in raw

    clean = attachments.clean_screenshot(upload(raw, "photo.jpg"))

    assert b"SECRET-CAMERA" not in clean.data
    assert (clean.extension, clean.content_type) == ("jpg", "image/jpeg")


def test_photo_taken_sideways_is_turned_upright(uploads: Path) -> None:
    exif = Image.Exif()
    exif[0x0112] = 6
    raw = image_bytes("JPEG", size=(80, 20), exif=exif)

    clean = attachments.clean_screenshot(upload(raw, "photo.jpg"))

    with Image.open(io.BytesIO(clean.data)) as image:
        assert image.size == (20, 80)


@pytest.mark.parametrize(
    ("image_format", "mode", "expected"),
    [
        ("PNG", "RGBA", "RGBA"),
        ("PNG", "L", "RGB"),
        ("PNG", "P", "RGB"),
        ("PNG", "LA", "RGBA"),
        ("JPEG", "CMYK", "RGB"),
        ("JPEG", "L", "RGB"),
    ],
)
def test_image_colour_types_are_accepted(
    uploads: Path, image_format: str, mode: str, expected: str
) -> None:
    clean = attachments.clean_screenshot(upload(image_bytes(image_format, mode=mode)))

    with Image.open(io.BytesIO(clean.data)) as image:
        assert image.mode == expected


@pytest.mark.parametrize(
    ("content", "name"),
    [
        (b"not an image at all", "screen.png"),
        (b"", "empty.png"),
        (b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", "a.png"),
        (b"<html><script>alert(1)</script></html>", "a.jpg"),
        (image_bytes("GIF"), "a.png"),
        (image_bytes("BMP"), "a.png"),
        (image_bytes()[:30], "cut-off.png"),
    ],
)
def test_files_that_are_not_real_images_are_refused(
    uploads: Path, content: bytes, name: str
) -> None:
    with pytest.raises(attachments.ScreenshotError) as refused:
        attachments.clean_screenshot(upload(content, name))

    assert "Only PNG or JPEG" in refused.value.message


def test_file_over_the_size_limit_is_refused(
    client: FlaskClient, uploads: Path
) -> None:
    client.application.config["MOH_FEEDBACK_SCREENSHOT_MAX_BYTES"] = 1024 * 1024

    with pytest.raises(attachments.ScreenshotError) as refused:
        attachments.clean_screenshot(upload(b"x" * (1024 * 1024 + 1)))

    assert "under 1 MB" in refused.value.message


def test_image_with_too_many_pixels_is_refused(
    client: FlaskClient, uploads: Path
) -> None:
    client.application.config["MOH_FEEDBACK_SCREENSHOT_MAX_PIXELS"] = 1000

    with pytest.raises(attachments.ScreenshotError) as refused:
        attachments.clean_screenshot(upload(image_bytes(size=(100, 100))))

    assert "too large" in refused.value.message


def test_too_many_files_are_refused(uploads: Path) -> None:
    files = [upload(image_bytes()) for _ in range(4)]

    with pytest.raises(attachments.ScreenshotError) as refused:
        attachments.prepare_screenshots(files)

    assert "up to 3" in refused.value.message


def test_unused_file_box_is_ignored(uploads: Path) -> None:
    assert attachments.prepare_screenshots([upload(b"", "")]) == []


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("../../etc/passwd.png", "passwd.png"),
        ("C:\\Users\\me\\screen.png", "screen.png"),
        ("a\x00b\nc.png", "abc.png"),
        ("   ", "screenshot"),
        ("x" * 400 + ".png", "x" * 255),
    ],
)
def test_file_names_are_made_safe(uploads: Path, name: str, expected: str) -> None:
    assert (
        attachments.clean_screenshot(upload(image_bytes(), name)).original_name
        == expected
    )


def test_stored_files_are_private_with_random_names(uploads: Path) -> None:
    clean = attachments.clean_screenshot(upload(image_bytes(), "my-secret-name.png"))

    stored = attachments.store_screenshots([clean])[0]

    path = uploads / stored.stored_name
    assert "my-secret-name" not in stored.stored_name
    assert path.read_bytes() == clean.data
    assert file_stat.S_IMODE(path.stat().st_mode) == 0o600
    assert file_stat.S_IMODE(uploads.stat().st_mode) == 0o700


def test_nothing_is_left_behind_when_saving_fails(uploads: Path) -> None:
    clean = attachments.clean_screenshot(upload(image_bytes()))
    real_open = attachments.os.open
    calls: list[int] = []

    def fail_second(*args: Any, **kwargs: Any) -> int:
        calls.append(1)
        if len(calls) == 2:
            raise OSError("disk full")
        return real_open(*args, **kwargs)

    with (
        mock.patch.object(attachments.os, "open", side_effect=fail_second),
        pytest.raises(attachments.ScreenshotError),
    ):
        attachments.store_screenshots([clean, clean])

    assert list(uploads.iterdir()) == []


def send_shots(
    client: FlaskClient, files: list[tuple[bytes, str]], **extra: str
) -> Any:
    data: dict[str, Any] = {
        **form_fields(client),
        "type": "problem",
        "message": MESSAGE,
        "direction": "up",
        "screenshots": [(io.BytesIO(content), name) for content, name in files],
        **extra,
    }
    return client.post("/moh/feedback/", data=data, content_type="multipart/form-data")


def stored_files(folder: Path) -> list[Path]:
    return list(folder.iterdir()) if folder.exists() else []


def test_form_offers_a_screenshot(client: FlaskClient, uploads: Path) -> None:
    html = client.get("/moh/feedback/new").get_data(as_text=True)

    assert 'enctype="multipart/form-data"' in html
    assert 'name="screenshots"' in html
    assert "Up to 3 PNG or JPEG images, 5 MB each" in html


def test_screenshots_are_saved_with_the_feedback(
    client: FlaskClient, session: Session, models: tuple[Any, Any], uploads: Path
) -> None:
    response = send_shots(
        client, [(image_bytes(), "one.png"), (image_bytes("JPEG"), "two.jpg")]
    )

    assert response.status_code == 302
    item = session.query(models[0]).one()
    assert [row.original_name for row in item.attachments] == ["one.png", "two.jpg"]
    assert len(stored_files(uploads)) == 2


def test_feedback_can_be_sent_without_a_screenshot(
    client: FlaskClient, session: Session, models: tuple[Any, Any], uploads: Path
) -> None:
    assert send_shots(client, []).status_code == 302

    assert session.query(models[0]).one().attachments == []
    assert stored_files(uploads) == []


def test_bad_file_stops_the_send_and_keeps_the_message(
    client: FlaskClient, session: Session, models: tuple[Any, Any], uploads: Path
) -> None:
    response = send_shots(
        client, [(image_bytes(), "good.png"), (b"not an image", "bad.png")]
    )

    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "Only PNG or JPEG" in html
    assert MESSAGE in html
    assert session.query(models[0]).count() == 0
    assert stored_files(uploads) == []


def test_oversized_upload_is_refused_before_reading_it(
    client: FlaskClient, session: Session, models: tuple[Any, Any], uploads: Path
) -> None:
    client.application.config["MOH_FEEDBACK_SCREENSHOT_MAX_BYTES"] = 1024
    client.application.config["MOH_FEEDBACK_MAX_SCREENSHOTS"] = 1

    response = send_shots(client, [(b"x" * (2 * 1024 * 1024), "big.png")])

    assert response.status_code == 413
    assert session.query(models[0]).count() == 0


def test_invalid_form_saves_no_screenshot(
    client: FlaskClient, session: Session, models: tuple[Any, Any], uploads: Path
) -> None:
    response = send_shots(client, [(image_bytes(), "a.png")], message="short")

    assert response.status_code == 400
    assert stored_files(uploads) == []


def test_refused_destination_saves_no_screenshot(
    client: FlaskClient, session: Session, models: tuple[Any, Any], uploads: Path
) -> None:
    response = send_shots(client, [(image_bytes(), "a.png")], direction="down")

    assert response.status_code == 400
    assert stored_files(uploads) == []


def test_failed_save_removes_the_screenshots(
    client: FlaskClient, session: Session, models: tuple[Any, Any], uploads: Path
) -> None:
    client.application.config["PROPAGATE_EXCEPTIONS"] = True

    with (
        mock.patch.object(views, "_save_feedback", side_effect=RuntimeError("db")),
        pytest.raises(RuntimeError),
    ):
        send_shots(client, [(image_bytes(), "a.png")])

    assert stored_files(uploads) == []


def test_same_form_sent_twice_keeps_one_set_of_files(
    client: FlaskClient, session: Session, models: tuple[Any, Any], uploads: Path
) -> None:
    fields = form_fields(client)

    for _ in range(2):
        client.post(
            "/moh/feedback/",
            data={
                **fields,
                "type": "problem",
                "message": MESSAGE,
                "direction": "up",
                "screenshots": [(io.BytesIO(image_bytes()), "a.png")],
            },
            content_type="multipart/form-data",
        )

    assert session.query(models[0]).count() == 1
    assert len(stored_files(uploads)) == 1


def item_with_shot(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> tuple[Any, Any]:
    send_shots(client, [(image_bytes(), "<b>name</b>.png")])
    item = session.query(models[0]).one()
    item.unit_access[0].unit_id = "unit-1"
    item.created_by_fk = 8
    session.commit()
    return item, item.attachments[0]


def attachment_url(row: Any) -> str:
    return f"/moh/feedback/attachment/{row.uuid}"


def test_handler_sees_the_screenshot(
    client: FlaskClient, session: Session, models: tuple[Any, Any], uploads: Path
) -> None:
    item, row = item_with_shot(client, session, models)

    html = detail(client, item).get_data(as_text=True)
    response = client.get(attachment_url(row))

    assert attachment_url(row) in html
    assert "<b>name</b>" not in html
    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "no-store" in response.headers["Cache-Control"]
    response.close()


def test_sender_sees_their_screenshot(
    client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    uploads: Path,
    user: SimpleNamespace,
) -> None:
    _, row = item_with_shot(client, session, models)
    user.id = 8

    with mock.patch.object(views, "get_user_units", return_value=[OTHER_UNIT]):
        response = client.get(attachment_url(row))

    assert response.status_code == 200
    response.close()


def test_stranger_cannot_open_a_screenshot(
    client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    uploads: Path,
    user: SimpleNamespace,
) -> None:
    _, row = item_with_shot(client, session, models)
    user.id = 30

    with mock.patch.object(views, "get_user_units", return_value=[OTHER_UNIT]):
        assert client.get(attachment_url(row)).status_code == 404


def test_screenshot_needs_a_sign_in(
    client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    uploads: Path,
    user: SimpleNamespace,
) -> None:
    _, row = item_with_shot(client, session, models)
    user.is_authenticated = False

    response = client.get(attachment_url(row))

    assert response.status_code == 302
    assert response.headers["Location"] == "/login/"


def test_screenshot_is_hidden_when_the_feature_is_off(
    client: FlaskClient, session: Session, models: tuple[Any, Any], uploads: Path
) -> None:
    _, row = item_with_shot(client, session, models)
    client.application.config["MOH_FEEDBACK_ENABLED"] = False

    assert client.get(attachment_url(row)).status_code == 404


def test_missing_or_unknown_screenshot_is_not_found(
    client: FlaskClient, session: Session, models: tuple[Any, Any], uploads: Path
) -> None:
    _, row = item_with_shot(client, session, models)
    (uploads / row.stored_name).unlink()

    assert client.get(attachment_url(row)).status_code == 404
    assert client.get(f"/moh/feedback/attachment/{uuid.uuid4()}").status_code == 404
    assert client.get("/moh/feedback/attachment/not-a-uuid").status_code == 404


def stat_item(**values: Any) -> SimpleNamespace:
    fields: dict[str, Any] = {
        "id": 1,
        "type": "problem",
        "status": "new",
        "closure_reason": None,
        "created_on": utc(2026, 11, 2, 8),
        "first_response_on": None,
        "first_response_due_on": None,
        "due_on": None,
        "origin_unit_id": "facility",
        "target_unit_id": "region",
        "target_unit_name": "Region",
        **{f"origin_level{level}id": None for level in range(1, 8)},
    }
    return SimpleNamespace(**{**fields, **values})


@pytest.mark.parametrize(
    ("values", "area", "expected"),
    [
        ({"origin_unit_id": "a"}, {"a"}, True),
        ({"origin_level3id": "a"}, {"a"}, True),
        ({"target_unit_id": "a"}, {"a"}, True),
        ({"target_unit_id": "below"}, {"region"}, True),
        ({"target_unit_id": "below"}, {"other"}, False),
        ({"target_unit_id": None}, {"other"}, False),
    ],
)
def test_item_counts_for_an_area(
    values: dict[str, Any], area: set[str], expected: bool
) -> None:
    below = OrgUnit("below", "Below", "Below", ("t", "region", "below"), False)

    assert stats.in_area(stat_item(**values), area, {"below": below}) is expected


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (60, "Under 1 hour"),
        (3600, "1 hour"),
        (7200, "2 hours"),
        (86400, "1 day"),
        (129600, "1.5 days"),
        (864000, "10 days"),
    ],
)
def test_time_is_described_simply(seconds: float, expected: str) -> None:
    assert stats.describe_duration(seconds) == expected


def test_summary_counts() -> None:
    now = utc(2026, 11, 20)
    due = utc(2026, 11, 10)
    items = [
        stat_item(
            id=1, first_response_on=utc(2026, 11, 2, 9), first_response_due_on=due
        ),
        stat_item(
            id=2, first_response_on=utc(2026, 11, 2, 11), first_response_due_on=due
        ),
        stat_item(id=3, first_response_on=utc(2026, 11, 12), first_response_due_on=due),
        stat_item(id=4, type="question", first_response_due_on=due),
        stat_item(
            id=5,
            type="question",
            status="closed",
            closure_reason="confirmed",
        ),
        stat_item(id=6, status="closed", closure_reason="no_response"),
        stat_item(id=7, status="closed", closure_reason="declined"),
    ]

    numbers = stats.summarise(items, {1, 99}, {"problem": "Problem"}, now)

    assert numbers.received == 7
    assert numbers.median_first_response == "3 hours"
    assert numbers.target_met_percent == 50
    assert numbers.overdue_now == 1
    assert dict(numbers.by_type) == {"Problem": 5, "question": 2}
    assert dict(numbers.outcomes) == {
        "Confirmed solved": 1,
        "Closed, no response": 1,
        "Declined": 1,
        "Still open": 4,
    }
    assert numbers.reopened == 1


def test_summary_of_nothing() -> None:
    numbers = stats.summarise([], set(), {}, utc(2026, 11, 20))

    assert numbers.received == 0
    assert numbers.median_first_response is None
    assert numbers.target_met_percent is None


def stats_html(client: FlaskClient, query: str = "") -> Any:
    with mock.patch.object(
        views, "get_units", side_effect=lambda ids: dict.fromkeys(ids) and {}
    ):
        return client.get(f"/moh/feedback/stats{query}")


def test_area_numbers_show_counts_but_no_messages(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    sent_to(session, models, message="A very private sentence.")
    item = session.query(models[0]).one()
    item.target_unit_id = UNIT.id
    session.commit()

    response = stats_html(client)
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "A very private sentence." not in html
    assert "<strong>1</strong><span>Received</span>" in html
    assert UNIT.path in html


def test_area_numbers_leave_out_other_areas(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    sent_to(session, models)
    item = session.query(models[0]).one()
    item.target_unit_id = "elsewhere"
    item.origin_unit_id = "elsewhere-too"
    session.commit()

    assert "No feedback was sent" in stats_html(client).get_data(as_text=True)


def test_area_numbers_respect_the_period(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    sent_to(session, models)
    item = session.query(models[0]).one()
    item.target_unit_id = UNIT.id
    item.created_on = datetime.utcnow() - timedelta(days=60)
    session.commit()

    assert "Received" not in stats_html(client, "?days=30").get_data(as_text=True)
    assert "Received" in stats_html(client, "?days=90").get_data(as_text=True)


@pytest.mark.parametrize("days", ["7", "abc", "-1", "99999"])
def test_unknown_period_falls_back_to_90_days(client: FlaskClient, days: str) -> None:
    html = stats_html(client, f"?days={days}").get_data(as_text=True)

    assert 'aria-current="true" href="/moh/feedback/stats?days=90"' in html


def test_area_numbers_are_only_for_handlers(
    client: FlaskClient, user: SimpleNamespace
) -> None:
    assert "Area numbers" in client.get("/moh/feedback/new").get_data(as_text=True)

    user.roles = [SimpleNamespace(name="Gamma")]

    assert stats_html(client).status_code == 404
    assert "Area numbers" not in client.get("/moh/feedback/new").get_data(as_text=True)


def test_area_numbers_need_a_sign_in(
    client: FlaskClient, user: SimpleNamespace
) -> None:
    user.is_authenticated = False

    response = stats_html(client)

    assert response.status_code == 302
    assert "/login/" in response.headers["Location"]


def test_area_numbers_are_hidden_when_the_feature_is_off(
    client: FlaskClient,
) -> None:
    client.application.config["MOH_FEEDBACK_ENABLED"] = False

    assert stats_html(client).status_code == 404


def test_area_numbers_wait_while_org_units_are_unavailable(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    sent_to(session, models)

    with mock.patch.object(views, "get_user_units", return_value=None):
        assert stats_html(client).status_code == 503
    with mock.patch.object(views, "get_units", side_effect=OrgUnitLookupError("x")):
        assert client.get("/moh/feedback/stats").status_code == 503


def test_multi_picture_phone_photo_is_accepted(uploads: Path) -> None:
    frame = Image.new("RGB", (60, 40), 90)
    output = io.BytesIO()
    frame.save(output, "MPO", save_all=True, append_images=[frame.copy()])

    clean = attachments.clean_screenshot(upload(output.getvalue(), "photo.jpg"))

    with Image.open(io.BytesIO(clean.data)) as image:
        assert (image.format, image.size) == ("JPEG", (60, 40))
    assert clean.content_type == "image/jpeg"


def test_image_decoder_failure_is_refused_politely(uploads: Path) -> None:
    with (
        mock.patch.object(attachments, "_redraw", side_effect=KeyError("broken")),
        pytest.raises(attachments.ScreenshotError),
    ):
        attachments.clean_screenshot(upload(image_bytes()))


def test_form_id_belonging_to_another_user_is_refused(
    client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
    uploads: Path,
) -> None:
    fields = form_fields(client)
    data = {"type": "problem", "message": MESSAGE, "direction": "up", **fields}
    assert client.post("/moh/feedback/", data=data).status_code == 302
    user.id = 8

    response = client.post(
        "/moh/feedback/",
        data={
            **data,
            "csrf_token": form_fields(client)["csrf_token"],
            "screenshots": [(io.BytesIO(image_bytes()), "a.png")],
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert session.query(models[0]).count() == 1
    assert stored_files(uploads) == []


def test_tabs_count_what_is_waiting(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    sent_to(session, models)
    sent_to(session, models)

    html = handled_client.get("/moh/feedback/new").get_data(as_text=True)

    assert 'title="Needs action">2</span>' in html
    assert 'title="Waiting for you"' not in html


def test_my_feedback_shows_what_needs_a_reply_first(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    asked = sent_to(session, models, message="Item with a question for me")
    act(handled_client, asked, "ask", message="Which month?")
    answered = sent_to(session, models, message="Item with an answer for me")
    act(handled_client, answered, "answer", message="Fixed.")
    sent_to(session, models, message="Newest item, nothing needed")
    user.id = 8

    html = handled_client.get("/moh/feedback/mine").get_data(as_text=True)

    assert html.index("for me") < html.index("Newest item")
    assert "Please reply" in html
    assert "Did this solve it?" in html
    assert 'title="Waiting for you">2</span>' in html


@pytest.mark.parametrize(
    ("referrer", "expected"),
    [
        ("http://localhost/superset/dashboard/12/?a=1", "/superset/dashboard/12/?a=1"),
        ("http://other.example/superset/dashboard/12/", None),
        ("http://localhost/moh/feedback/mine", None),
        ("http://localhost/feedback/", None),
        (None, None),
    ],
)
def test_form_records_the_page_the_user_came_from(
    client: FlaskClient, referrer: str | None, expected: str | None
) -> None:
    headers = {"Referer": referrer} if referrer else {}

    html = client.get("/moh/feedback/new", headers=headers).get_data(as_text=True)

    assert _hidden_value(html, "page_url") == (expected or "").replace("&", "&amp;")


def test_page_is_shown_by_its_dashboard_name(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)
    item.page_url = "/superset/dashboard/12/"
    session.commit()

    with mock.patch.object(views, "_page_title", return_value="Malaria Overview"):
        html = detail(client, item).get_data(as_text=True)

    assert ">Malaria Overview</a>" in html


def test_sender_is_told_when_to_expect_a_reply(
    client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    send_with(client, [])
    item = session.query(models[0]).one()

    html = client.get("/moh/feedback/new").get_data(as_text=True)

    day = deadlines.local_date(item.first_response_due_on)
    assert f"You should hear back by <strong>{day.day} {day:%b %Y}</strong>" in html


def test_handler_can_message_the_sender_without_changing_status(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = started_item(session, models)

    assert (
        act(mail_client, item, "reply", message="We are checking.").status_code == 302
    )

    assert item.status == "new"
    assert item.first_response_on is not None
    assert [(row.kind, row.user_id) for row in queued(session)] == [
        ("handler_reply", 8)
    ]
    user.id = 8
    assert "We are checking." in detail(mail_client, item).get_data(as_text=True)


def test_handler_can_still_write_after_answering(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = started_item(session, models)
    act(handled_client, item, "answer", message="Done.")

    assert (
        act(handled_client, item, "reply", message="One more thing.").status_code == 302
    )
    assert item.status == "answered"


def test_sender_information_reaches_the_handlers(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = started_item(session, models)
    user.id = 8

    assert reply(mail_client, item, "Extra details.").status_code == 302

    row = queued(session)[-1]
    assert (row.kind, row.unit_id) == ("sender_message", "unit-1")


@pytest.mark.parametrize("action", ["answer", "decline"])
def test_sender_cannot_write_once_answered_or_closed(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
    action: str,
) -> None:
    item = started_item(session, models)
    act(handled_client, item, action, message="Finished.")
    user.id = 8

    response = handled_client.post(
        f"/moh/feedback/{item.uuid}/reply",
        data={
            "csrf_token": form_fields(handled_client)["csrf_token"],
            "message": "More.",
        },
    )

    assert response.status_code == 409


def hide(client: FlaskClient, item: Any, target: str) -> Any:
    return client.post(
        f"/moh/feedback/{item.uuid}/hide",
        data={"csrf_token": form_fields(client)["csrf_token"], "target": target},
    )


def test_message_with_patient_details_can_be_hidden(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = sent_to(session, models, message="Patient Abebe has the wrong figure")

    assert hide(handled_client, item, "message").status_code == 302

    assert item.hidden_on is not None
    assert (item.events[-1].event_type, item.events[-1].actor_name) == (
        "content_hidden",
        "Sample User",
    )
    for viewer in (7, 8):
        user.id = viewer
        page = detail(handled_client, item).get_data(as_text=True)
        assert "Patient Abebe" not in page
        assert "Hidden because it may contain patient details." in page
    user.id = 7
    assert "Patient Abebe" not in waiting_html(handled_client)
    user.id = 8
    assert "Patient Abebe" not in handled_client.get("/moh/feedback/mine").get_data(
        as_text=True
    )


def test_history_entry_can_be_hidden(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)
    act(handled_client, item, "reply", message="Patient details in a reply")
    event = item.events[-1]

    assert hide(handled_client, item, f"event-{event.id}").status_code == 302

    assert "Patient details in a reply" not in detail(handled_client, item).get_data(
        as_text=True
    )


def test_hidden_screenshot_can_no_longer_be_opened(
    client: FlaskClient, session: Session, models: tuple[Any, Any], uploads: Path
) -> None:
    item, row = item_with_shot(client, session, models)

    assert hide(client, item, f"attachment-{row.id}").status_code == 302

    assert row.hidden_on is not None
    assert client.get(attachment_url(row)).status_code == 404
    assert attachment_url(row) not in detail(client, item).get_data(as_text=True)


@pytest.mark.parametrize(
    "target", ["", "other", "event-999", "attachment-1", "message-1"]
)
def test_hide_needs_a_real_target(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    target: str,
) -> None:
    item = sent_to(session, models)

    assert hide(handled_client, item, target).status_code == 409
    assert item.hidden_on is None


def test_hiding_twice_is_told(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)
    hide(handled_client, item, "message")

    assert hide(handled_client, item, "message").status_code == 409


def test_only_the_responsible_unit_can_hide(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = sent_to(session, models)
    user.id = 8
    assert "Hide (contains" not in detail(handled_client, item).get_data(as_text=True)
    assert hide(handled_client, item, "message").status_code == 403
    assert item.hidden_on is None

    user.id = 30
    with mock.patch.object(views, "get_user_units", return_value=[OTHER_UNIT]):
        assert hide(handled_client, item, "message").status_code == 404


def closed_item(
    client: FlaskClient, session: Session, models: tuple[Any, Any], user: Any
) -> Any:
    item = started_item(session, models)
    act(client, item, "answer", message="Done.")
    user.id = 8
    decide(client, item, "solved")
    return item


def reopen(client: FlaskClient, item: Any, message: str = "Still broken.") -> Any:
    return client.post(
        f"/moh/feedback/{item.uuid}/reopen",
        data={"csrf_token": form_fields(client)["csrf_token"], "message": message},
    )


def test_sender_can_reopen_a_closed_item(
    mail_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = closed_item(mail_client, session, models, user)
    assert "Reopen this feedback" in detail(mail_client, item).get_data(as_text=True)

    assert reopen(mail_client, item).status_code == 302

    assert item.status == "in_review"
    assert (item.closed_on, item.closure_reason, item.answered_on) == (None, None, None)
    assert item.due_on > datetime.utcnow()
    assert history(item)[-1] == "reopened"
    assert queued(session)[-1].kind == "reopened"


def test_item_cannot_be_reopened_after_the_time_limit(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = closed_item(handled_client, session, models, user)
    item.closed_on = datetime.utcnow() - timedelta(days=31)
    session.commit()

    assert "Reopen this feedback" not in detail(handled_client, item).get_data(
        as_text=True
    )
    assert reopen(handled_client, item).status_code == 409
    assert item.status == "closed"


def test_reopen_needs_a_reason(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = closed_item(handled_client, session, models, user)

    assert reopen(handled_client, item, "   ").status_code == 400
    assert item.status == "closed"


def test_only_the_sender_can_reopen(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = closed_item(handled_client, session, models, user)
    user.id = 7

    assert reopen(handled_client, item).status_code == 404


def test_open_item_cannot_be_reopened(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    item = started_item(session, models)
    user.id = 8

    assert reopen(handled_client, item).status_code == 409


def listed(client: FlaskClient, query: str) -> str:
    return client.get(f"/moh/feedback/waiting?view=all&{query}").get_data(as_text=True)


@pytest.mark.parametrize("term", ["malaria", "MALARIA"])
def test_search_finds_words_in_any_capitalisation(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    term: str,
) -> None:
    sent_to(session, models, message="The malaria chart is wrong here")
    sent_to(session, models, message="The delivery chart is fine here")

    html = listed(handled_client, f"q={term}")

    assert "malaria chart" in html
    assert "delivery chart" not in html


@pytest.mark.parametrize("prefix", ["FB-", "fb", ""])
def test_search_finds_a_reference(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    prefix: str,
) -> None:
    item = sent_to(session, models, message="Item to be found here")
    sent_to(session, models, message="Item not to be matched")

    html = listed(handled_client, f"q={prefix}{item.id}")

    assert "Item to be found" in html
    assert "not to be matched" not in html


def test_search_treats_special_characters_literally(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    sent_to(session, models, message="A message about nothing special")

    assert "Nothing matches your search." in listed(handled_client, "q=%25")
    assert "Nothing matches your search." in listed(handled_client, "q=_")


def test_search_does_not_find_hidden_text(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models, message="Patient Abebe has the wrong figure")
    hide(handled_client, item, "message")

    assert "Nothing matches your search." in listed(handled_client, "q=Abebe")


def test_status_filter(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    asked = sent_to(session, models, message="This one was asked about")
    act(handled_client, asked, "ask", message="Which month?")
    sent_to(session, models, message="This one is still new")

    html = listed(handled_client, "status=needs_info")

    assert "was asked about" in html
    assert "still new" not in html


def test_overdue_filter(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    overdue_item(session, models, message="This one is past its date")
    started_item(session, models, message="This one has no date yet")

    html = listed(handled_client, "status=overdue")

    assert "past its date" in html
    assert "no date yet" not in html


def test_unknown_status_filter_is_ignored(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    sent_to(session, models, message="Still shown on the page")

    assert "Still shown" in listed(handled_client, "status=nonsense")


def test_page_links_keep_the_search(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    for _ in range(26):
        sent_to(session, models, message="Repeated malaria message")

    assert "q=malaria" in listed(handled_client, "q=malaria").split('class="pager"')[1]


def test_my_feedback_can_be_searched(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
    user: SimpleNamespace,
) -> None:
    sent_to(session, models, message="The malaria chart is wrong")
    sent_to(session, models, message="The delivery chart is fine")
    user.id = 8

    html = handled_client.get("/moh/feedback/mine?q=malaria").get_data(as_text=True)

    assert "malaria chart" in html
    assert "delivery chart" not in html


def test_work_assigned_to_a_departed_user_returns_to_needs_action(
    handled_client: FlaskClient,
    session: Session,
    models: tuple[Any, Any],
) -> None:
    from flask_appbuilder.security.sqla.models import User

    session.add(
        User(
            id=9,
            first_name="Gone",
            last_name="User",
            username="gone",
            email="gone@mail.test",
            active=False,
        )
    )
    session.commit()
    item = sent_to(session, models, message="Assigned to someone who left")
    act(handled_client, item, "assign", assignee_id="9")

    assert "Assigned to someone who left" in waiting_html(handled_client)


def test_list_shows_who_it_is_assigned_to_and_the_office_name_only(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    item = sent_to(session, models)
    item.origin_path = "Federal › Region › Sample Facility"
    session.commit()
    act(handled_client, item, "assign", assignee_id="9")

    html = listed(handled_client, "")

    assert "Other Handler" in html
    assert '<div class="hint">Sample Facility</div>' in html


def test_area_numbers_show_where_items_wait() -> None:
    now = utc(2026, 11, 20)
    items = [
        stat_item(
            id=1,
            target_unit_name="Office A",
            created_on=utc(2026, 11, 10),
            due_on=utc(2026, 11, 12),
        ),
        stat_item(id=2, target_unit_name="Office B", created_on=utc(2026, 11, 18)),
        stat_item(id=3, target_unit_name="Office B", created_on=utc(2026, 11, 19)),
        stat_item(id=4, target_unit_name="Office C", status="closed"),
        stat_item(id=5, target_unit_id=None, target_unit_name=None),
    ]

    offices = stats.summarise(items, set(), {}, now).by_office

    assert [(o.name, o.open_items, o.overdue, o.oldest_days) for o in offices] == [
        ("Office A", 1, 1, 10),
        ("Office B", 2, 0, 2),
    ]


def test_search_ignores_invalid_characters(
    handled_client: FlaskClient, session: Session, models: tuple[Any, Any]
) -> None:
    sent_to(session, models, message="The malaria chart is wrong here")

    response = handled_client.get(
        "/moh/feedback/waiting", query_string={"q": "mala\x00ria"}
    )

    assert response.status_code == 200
    assert "malaria chart" in response.get_data(as_text=True)
