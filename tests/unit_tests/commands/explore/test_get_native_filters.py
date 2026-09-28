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

"""Tests for the parent dashboard's native filter configuration in Explore."""

from unittest.mock import MagicMock, patch

import pytest

from superset.commands.dashboard.exceptions import (
    DashboardAccessDeniedError,
    DashboardNotFoundError,
)
from superset.commands.explore.get import GetExploreCommand
from superset.commands.explore.parameters import CommandParameters
from superset.utils import json

FILTERS = [
    {"id": "NATIVE_FILTER-region", "name": "Region", "filterType": "NATIVE_FILTER"},
    {"id": "DIVIDER-x", "type": "DIVIDER"},
]


def _command(**overrides) -> GetExploreCommand:
    params = CommandParameters(
        permalink_key=None,
        form_data_key=None,
        datasource_id=1,
        datasource_type="table",
        slice_id=1,
        **overrides,
    )
    return GetExploreCommand(params)


def _dashboard(json_metadata: str | None) -> MagicMock:
    dashboard = MagicMock()
    dashboard.id = 7
    dashboard.json_metadata = json_metadata
    return dashboard


def test_no_configuration_without_dashboard_id():
    """Explore opened outside a dashboard has no filter configuration."""
    assert _command()._get_native_filter_configuration() is None


def test_dashboard_id_defaults_to_none():
    """Existing callers that omit dashboard_id keep working unchanged."""
    assert (
        CommandParameters(
            permalink_key=None,
            form_data_key=None,
            datasource_id=1,
            datasource_type="table",
            slice_id=1,
        ).dashboard_id
        is None
    )


def test_returns_dashboard_native_filters():
    """The dashboard's own filter configuration is handed to Explore."""
    dashboard = _dashboard(json.dumps({"native_filter_configuration": FILTERS}))

    with patch(
        "superset.commands.explore.get.DashboardDAO.get_by_id_or_slug",
        return_value=dashboard,
    ) as get_by_id_or_slug:
        assert _command(dashboard_id=7)._get_native_filter_configuration() == FILTERS

    get_by_id_or_slug.assert_called_once_with(7)


def test_returns_none_when_dashboard_has_no_filters():
    dashboard = _dashboard(json.dumps({"other_key": "value"}))

    with patch(
        "superset.commands.explore.get.DashboardDAO.get_by_id_or_slug",
        return_value=dashboard,
    ):
        assert _command(dashboard_id=7)._get_native_filter_configuration() is None


def test_returns_none_without_json_metadata():
    dashboard = _dashboard(None)

    with patch(
        "superset.commands.explore.get.DashboardDAO.get_by_id_or_slug",
        return_value=dashboard,
    ):
        assert _command(dashboard_id=7)._get_native_filter_configuration() is None


def test_returns_none_when_json_metadata_is_malformed():
    """A dashboard with unparseable metadata must not break Explore."""
    dashboard = _dashboard("{not json")

    with patch(
        "superset.commands.explore.get.DashboardDAO.get_by_id_or_slug",
        return_value=dashboard,
    ):
        assert _command(dashboard_id=7)._get_native_filter_configuration() is None


def test_returns_none_when_configuration_is_not_a_list():
    dashboard = _dashboard(json.dumps({"native_filter_configuration": "nope"}))

    with patch(
        "superset.commands.explore.get.DashboardDAO.get_by_id_or_slug",
        return_value=dashboard,
    ):
        assert _command(dashboard_id=7)._get_native_filter_configuration() is None


@pytest.mark.parametrize(
    "error",
    [DashboardNotFoundError("gone"), DashboardAccessDeniedError("nope")],
)
def test_returns_none_when_dashboard_is_unreadable(error):
    """A missing or forbidden dashboard yields no configuration, not an error."""
    with patch(
        "superset.commands.explore.get.DashboardDAO.get_by_id_or_slug",
        side_effect=error,
    ):
        assert _command(dashboard_id=7)._get_native_filter_configuration() is None
