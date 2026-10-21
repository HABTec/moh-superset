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
from typing import Any, cast
from unittest.mock import patch

import pytest
from flask import Flask

from superset import moh_tab_access
from superset.errors import ErrorLevel, SupersetError, SupersetErrorType
from superset.exceptions import SupersetSecurityException
from superset.models.dashboard import Dashboard
from superset.moh_security_manager import MoHSecurityManager
from superset.utils import json

AMHARA_WOREDA = "/b3aCK1PTn5S/yb9NKGA8uqt/woreda1"
DIRE_DAWA_FACILITY = "/b3aCK1PTn5S/G9hDiPNoB7d/woreda2/facility3"


def _tab(key: str, title: str, children: list[str]) -> dict[str, Any]:
    return {"id": key, "type": "TAB", "meta": {"text": title}, "children": children}


def _chart(key: str, chart_id: int) -> dict[str, Any]:
    return {"id": key, "type": "CHART", "meta": {"chartId": chart_id}, "children": []}


LAYOUT: dict[str, Any] = {
    "DASHBOARD_VERSION_KEY": "v2",
    "ROOT_ID": {"id": "ROOT_ID", "type": "ROOT", "children": ["TABS-1"]},
    "TABS-1": {
        "id": "TABS-1",
        "type": "TABS",
        "children": ["TAB-summary", "TAB-multi", "TAB-tri"],
    },
    "TAB-summary": _tab("TAB-summary", "Summary", ["CHART-1", "CHART-shared"]),
    "TAB-multi": _tab("TAB-multi", "Multi Source", ["TABS-2"]),
    "TABS-2": {"id": "TABS-2", "type": "TABS", "children": ["TAB-wuenic"]},
    "TAB-wuenic": _tab("TAB-wuenic", "WUENIC", ["CHART-29", "CHART-shared-2"]),
    "TAB-tri": _tab("TAB-tri", "Triangulation", ["CHART-27"]),
    "CHART-1": _chart("CHART-1", 1),
    "CHART-shared": _chart("CHART-shared", 50),
    "CHART-29": _chart("CHART-29", 29),
    "CHART-shared-2": _chart("CHART-shared-2", 50),
    "CHART-27": _chart("CHART-27", 27),
}


def _dashboard(dashboard_id: int = 3) -> Dashboard:
    return cast(
        Dashboard, SimpleNamespace(id=dashboard_id, position_json=json.dumps(LAYOUT))
    )


@pytest.fixture
def request_context():
    app = Flask(__name__)
    with app.test_request_context("/"):
        yield


def _as_user(path: str, sees_all: bool = False):
    return (
        patch.object(moh_tab_access, "_sees_all_tabs", return_value=sees_all),
        patch.object(moh_tab_access, "_user_org_unit_path", return_value=path),
    )


def test_level_one_users_see_every_tab(request_context) -> None:
    sees_all, path = _as_user("", sees_all=True)
    with sees_all, path:
        assert moh_tab_access.hidden_tab_ids(_dashboard()) == set()


def test_regional_users_lose_multi_source_and_triangulation(request_context) -> None:
    sees_all, path = _as_user(AMHARA_WOREDA)
    with sees_all, path:
        dashboard = _dashboard()
        assert moh_tab_access.hidden_tab_ids(dashboard) == {"TAB-multi", "TAB-tri"}
        # Chart 50 also sits on the Summary tab, so it stays available.
        assert moh_tab_access.hidden_chart_ids(dashboard) == {29, 27}

        result = moh_tab_access.restrict_dashboard_result(
            dashboard, {"id": 3, "position_json": dashboard.position_json}
        )
    layout = json.loads(result["position_json"])
    assert layout["TABS-1"]["children"] == ["TAB-summary"]
    assert not {"TAB-multi", "TABS-2", "TAB-wuenic", "CHART-29", "TAB-tri"} & set(
        layout
    )
    assert layout["CHART-shared"] == LAYOUT["CHART-shared"]


def test_dire_dawa_users_keep_triangulation(request_context) -> None:
    sees_all, path = _as_user(DIRE_DAWA_FACILITY)
    with sees_all, path:
        assert moh_tab_access.hidden_tab_ids(_dashboard()) == {"TAB-multi"}


def test_users_without_an_org_unit_see_only_open_tabs(request_context) -> None:
    sees_all, path = _as_user("")
    with sees_all, path:
        assert moh_tab_access.hidden_tab_ids(_dashboard()) == {"TAB-multi", "TAB-tri"}


def test_other_dashboards_are_unchanged(request_context) -> None:
    sees_all, path = _as_user(AMHARA_WOREDA)
    with sees_all as sees_all_mock, path:
        assert moh_tab_access.hidden_tab_ids(_dashboard(8)) == set()
        sees_all_mock.assert_not_called()


def test_restricted_tabs_follow_the_configuration() -> None:
    app = Flask(__name__)
    app.config["MOH_RESTRICTED_TABS"] = {"8": {"  supply  and logistics": []}}
    with app.test_request_context("/"):
        assert moh_tab_access._restricted_tabs(8) == {"supply and logistics": []}
        assert moh_tab_access._restricted_tabs(3) == {}


def test_tab_list_drops_hidden_tabs(request_context) -> None:
    tabs = {
        "all_tabs": {"TAB-summary": "Summary", "TAB-multi": "Multi Source"},
        "tab_tree": [
            {"value": "TAB-summary", "title": "Summary", "children": []},
            {
                "value": "TAB-multi",
                "title": "Multi Source",
                "children": [{"value": "TAB-wuenic", "children": []}],
            },
        ],
    }
    with patch.object(moh_tab_access, "hidden_tab_ids", return_value={"TAB-multi"}):
        result = moh_tab_access.restrict_tabs_result(_dashboard(), tabs)

    assert result["all_tabs"] == {"TAB-summary": "Summary"}
    assert [node["value"] for node in result["tab_tree"]] == ["TAB-summary"]


def test_chart_data_for_a_hidden_tab_is_refused(request_context) -> None:
    manager = object.__new__(MoHSecurityManager)
    manager.get_dashboard_access_error_object = lambda dashboard: SupersetError(  # type: ignore[method-assign]
        error_type=SupersetErrorType.DASHBOARD_SECURITY_ACCESS_ERROR,
        message="denied",
        level=ErrorLevel.WARNING,
    )
    manager._level_one_dashboard_ids = lambda: {8}  # type: ignore[method-assign]
    dashboard = _dashboard()

    def query_context(slice_id: int) -> SimpleNamespace:
        return SimpleNamespace(form_data={"dashboardId": 3, "slice_id": slice_id})

    with (
        patch.object(moh_tab_access, "hidden_chart_ids", return_value={29, 27}),
        patch("superset.moh_security_manager.db") as db,
        patch(
            "superset.moh_security_manager.SupersetSecurityManager.raise_for_access"
        ) as rbac_check,
    ):
        db.session.get.return_value = dashboard
        with pytest.raises(SupersetSecurityException):
            manager.raise_for_access(query_context=query_context(29))
        rbac_check.assert_not_called()

        manager.raise_for_access(query_context=query_context(1))
        rbac_check.assert_called_once()
