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
from types import SimpleNamespace
from typing import Any

from flask import Flask, g

from superset.moh_security_manager import MoHSecurityManager


def test_level_one_dashboard_ids_supports_configured_csv() -> None:
    app = Flask(__name__)
    app.config["MOH_LEVEL_ONE_DASHBOARD_IDS"] = "8, 12"
    manager = object.__new__(MoHSecurityManager)

    with app.app_context():
        assert manager._level_one_dashboard_ids() == {8, 12}


def test_non_restricted_dashboard_is_accessible_without_org_unit() -> None:
    app = Flask(__name__)
    app.config["MOH_LEVEL_ONE_DASHBOARD_IDS"] = {8}
    manager = object.__new__(MoHSecurityManager)
    manager.is_admin = lambda: False

    with app.app_context():
        assert manager.can_access_moh_dashboard(SimpleNamespace(id=3))


def test_level_one_user_can_access_restricted_dashboard() -> None:
    app = Flask(__name__)
    app.config["MOH_LEVEL_ONE_DASHBOARD_IDS"] = {8}
    manager = object.__new__(MoHSecurityManager)
    manager.is_admin = lambda: False
    manager._user_has_level_one_org_unit = lambda username: username == "moh_user"

    with app.test_request_context("/"):
        g.user = SimpleNamespace(username="moh_user", is_anonymous=False)

        assert manager.can_access_moh_dashboard(SimpleNamespace(id=8))


def test_non_level_one_user_denied_restricted_dashboard() -> None:
    app = Flask(__name__)
    app.config["MOH_LEVEL_ONE_DASHBOARD_IDS"] = {8}
    manager = object.__new__(MoHSecurityManager)
    manager.is_admin = lambda: False
    manager._user_has_level_one_org_unit = lambda username: False

    with app.test_request_context("/"):
        g.user = SimpleNamespace(username="region_user", is_anonymous=False)

        assert not manager.can_access_moh_dashboard(SimpleNamespace(id=8))


def test_allowlisted_guest_username_can_access_restricted_dashboard() -> None:
    app = Flask(__name__)
    app.config["MOH_LEVEL_ONE_DASHBOARD_IDS"] = {8}
    app.config["MOH_LEVEL_ONE_GUEST_USERNAMES"] = {"tvp-guest"}
    manager = object.__new__(MoHSecurityManager)
    manager.is_admin = lambda: False
    # No org-unit row for a guest identity; the allowlist must be what grants access.
    manager._user_has_level_one_org_unit = lambda username: False

    with app.test_request_context("/"):
        g.user = SimpleNamespace(username="tvp-guest", is_anonymous=False)

        assert manager.can_access_moh_dashboard(SimpleNamespace(id=8))


def test_non_allowlisted_guest_username_denied_restricted_dashboard() -> None:
    app = Flask(__name__)
    app.config["MOH_LEVEL_ONE_DASHBOARD_IDS"] = {8}
    app.config["MOH_LEVEL_ONE_GUEST_USERNAMES"] = {"tvp-guest"}
    manager = object.__new__(MoHSecurityManager)
    manager.is_admin = lambda: False
    manager._user_has_level_one_org_unit = lambda username: False

    with app.test_request_context("/"):
        g.user = SimpleNamespace(username="some-other-guest", is_anonymous=False)

        assert not manager.can_access_moh_dashboard(SimpleNamespace(id=8))


def test_guest_allowlist_supports_configured_csv() -> None:
    app = Flask(__name__)
    app.config["MOH_LEVEL_ONE_GUEST_USERNAMES"] = "tvp-guest, other-guest"
    manager = object.__new__(MoHSecurityManager)

    with app.app_context():
        assert manager._level_one_guest_usernames() == {"tvp-guest", "other-guest"}


def test_guest_allowlist_empty_by_default() -> None:
    app = Flask(__name__)
    manager = object.__new__(MoHSecurityManager)

    with app.app_context():
        assert manager._level_one_guest_usernames() == set()


def test_raise_for_access_reads_dashboard_id_from_form_data() -> None:
    app = Flask(__name__)
    app.config["MOH_LEVEL_ONE_DASHBOARD_IDS"] = {8}
    manager = object.__new__(MoHSecurityManager)
    manager.is_admin = lambda: False
    manager._user_has_level_one_org_unit = lambda username: False

    from superset.errors import ErrorLevel, SupersetError, SupersetErrorType
    from superset.exceptions import SupersetSecurityException

    manager.get_dashboard_access_error_object = lambda dashboard: SupersetError(
        error_type=SupersetErrorType.DASHBOARD_SECURITY_ACCESS_ERROR,
        message="denied",
        level=ErrorLevel.WARNING,
    )

    class _QueryContext:
        form_data = {"dashboardId": 8}

    with app.test_request_context("/"):
        g.user = SimpleNamespace(username="region_user", is_anonymous=False)
        try:
            manager.raise_for_access(query_context=_QueryContext())
            raised = False
        except SupersetSecurityException:
            raised = True

        assert raised


def _datasource_manager(monkeypatch, level_one_user: bool):
    from superset.errors import ErrorLevel, SupersetError, SupersetErrorType
    from superset.security.manager import SupersetSecurityManager

    monkeypatch.setattr(
        SupersetSecurityManager, "raise_for_access", lambda self, *a, **k: None
    )
    manager = object.__new__(MoHSecurityManager)
    manager.is_admin = lambda: False
    manager._user_has_level_one_org_unit = lambda username: level_one_user
    manager._level_one_only_dataset_ids = lambda: {24}
    manager.get_datasource_access_error_object = lambda datasource: SupersetError(
        error_type=SupersetErrorType.DATASOURCE_SECURITY_ACCESS_ERROR,
        message="denied",
        level=ErrorLevel.WARNING,
    )
    return manager


def _query_context(
    dataset_id: int, form_data: dict[str, Any] | None = None
) -> SimpleNamespace:
    return SimpleNamespace(
        form_data=form_data or {},
        datasource=SimpleNamespace(id=dataset_id, type="table"),
    )


def test_level_one_dataset_denied_without_dashboard_id(monkeypatch) -> None:
    from superset.exceptions import SupersetSecurityException

    app = Flask(__name__)
    app.config["MOH_LEVEL_ONE_DASHBOARD_IDS"] = {8}
    manager = _datasource_manager(monkeypatch, level_one_user=False)

    with app.test_request_context("/"):
        g.user = SimpleNamespace(username="region_user", is_anonymous=False)
        for kwargs in (
            {"query_context": _query_context(24)},
            {"query_context": _query_context(24, {"dashboardId": 3})},
            {"datasource": SimpleNamespace(id=24, type="table")},
            {"chart": SimpleNamespace(datasource=SimpleNamespace(id=24, type="table"))},
        ):
            try:
                manager.raise_for_access(**kwargs)
                raised = False
            except SupersetSecurityException:
                raised = True
            assert raised, kwargs


def test_level_one_dataset_allowed_for_level_one_user_and_admin(monkeypatch) -> None:
    app = Flask(__name__)
    app.config["MOH_LEVEL_ONE_DASHBOARD_IDS"] = {8}
    manager = _datasource_manager(monkeypatch, level_one_user=True)

    with app.test_request_context("/"):
        g.user = SimpleNamespace(username="moh_user", is_anonymous=False)
        manager.raise_for_access(query_context=_query_context(24))

    admin = _datasource_manager(monkeypatch, level_one_user=False)
    admin.is_admin = lambda: True
    with app.test_request_context("/"):
        g.user = SimpleNamespace(username="admin", is_anonymous=False)
        admin.raise_for_access(query_context=_query_context(24))


def test_shared_dataset_left_to_rbac(monkeypatch) -> None:
    app = Flask(__name__)
    app.config["MOH_LEVEL_ONE_DASHBOARD_IDS"] = {8}
    manager = _datasource_manager(monkeypatch, level_one_user=False)

    with app.test_request_context("/"):
        g.user = SimpleNamespace(username="region_user", is_anonymous=False)
        manager.raise_for_access(query_context=_query_context(5))
        manager.raise_for_access(datasource=SimpleNamespace(id=24, type="query"))


def test_level_one_only_dataset_ids_excludes_datasets_on_other_dashboards(
    monkeypatch,
) -> None:
    import superset.moh_security_manager as module
    from superset.utils import json

    chart_rows = [(8, 24), (8, 25), (8, 5), (3, 5), (1, 7), (8, None)]
    # Dashboard 3 filters on dataset 25; dashboard 8 filters on dataset 44 only.
    dashboard_rows = [
        (
            3,
            json.dumps(
                {"native_filter_configuration": [{"targets": [{"datasetId": 25}]}]}
            ),
        ),
        (
            8,
            json.dumps(
                {"native_filter_configuration": [{"targets": [{"datasetId": 44}, {}]}]}
            ),
        ),
        (1, None),
    ]

    class _Query:
        def __init__(self, rows):
            self.rows = rows

        def join(self, *a, **k):
            return self

        def filter(self, *a, **k):
            return self

        def all(self):
            return list(self.rows)

    def query(*columns):
        return _Query(
            dashboard_rows
            if len(columns) == 2 and "json_metadata" in str(columns[1])
            else chart_rows
        )

    monkeypatch.setattr(
        module, "db", SimpleNamespace(session=SimpleNamespace(query=query))
    )
    app = Flask(__name__)
    app.config["MOH_LEVEL_ONE_DASHBOARD_IDS"] = {8}
    app.config["MOH_LEVEL_ONE_CACHE_TTL"] = 0
    manager = object.__new__(MoHSecurityManager)

    with app.test_request_context("/"):
        assert manager._level_one_only_dataset_ids() == {24, 44}
