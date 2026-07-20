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
"""MoH-specific dashboard authorization based on a user's org-unit level."""

from __future__ import annotations

import logging
from typing import Any

from flask import current_app
from sqlalchemy import text

from superset import db
from superset.exceptions import SupersetSecurityException
from superset.security.manager import SupersetSecurityManager
from superset.tasks.utils import get_current_user

logger = logging.getLogger(__name__)


def _quote_identifier(identifier: str) -> str:
    """Quote a configured SQL identifier for a ClickHouse query."""
    return '"' + identifier.replace('"', '""') + '"'


class MoHSecurityManager(SupersetSecurityManager):
    """Apply MoH dashboard restrictions before Superset's standard checks."""

    def _level_one_dashboard_ids(self) -> set[int]:
        """Return dashboard IDs whose access is reserved for level-one users."""
        configured_ids = current_app.config.get("MOH_LEVEL_ONE_DASHBOARD_IDS", ())
        if isinstance(configured_ids, str):
            configured_ids = configured_ids.split(",")
        try:
            return {int(dashboard_id) for dashboard_id in configured_ids}
        except (TypeError, ValueError):
            logger.error("MOH_LEVEL_ONE_DASHBOARD_IDS contains an invalid dashboard ID")
            return set()

    def _user_has_level_one_org_unit(self, username: str) -> bool:
        """Return whether ``username`` is assigned to a level-one org unit."""
        database_name = current_app.config.get(
            "MOH_ORG_UNITS_DB_NAME", "MOH_Click_Hhouse"
        )
        schema = current_app.config.get("MOH_ORG_UNITS_SCHEMA", "moh")
        user_org_units_schema = current_app.config.get(
            "MOH_USER_ORG_UNITS_SCHEMA", schema
        )
        org_units_table = current_app.config.get("MOH_ORG_UNITS_TABLE", "org_units")
        user_org_units_table = current_app.config.get(
            "MOH_USER_ORG_UNITS_TABLE", "dim_user_orgunit"
        )

        from superset.models.core import Database

        database = (
            db.session.query(Database)
            .filter_by(database_name=database_name)
            .first()
        )
        if database is None:
            logger.error("MoH org-unit database %r is not configured", database_name)
            return False

        org_units_prefix = f"{_quote_identifier(str(schema))}." if schema else ""
        user_org_units_prefix = (
            f"{_quote_identifier(str(user_org_units_schema))}."
            if user_org_units_schema
            else ""
        )
        org_units = f"{org_units_prefix}{_quote_identifier(str(org_units_table))}"
        user_org_units = (
            f"{user_org_units_prefix}{_quote_identifier(str(user_org_units_table))}"
        )
        query = text(
            "SELECT org_unit.level "
            f"FROM {user_org_units} AS user_org_unit "
            f"INNER JOIN {org_units} AS org_unit "
            "ON user_org_unit.org_unit_id = org_unit.id "
            "WHERE user_org_unit.username = :username "
            "AND org_unit.level = 1 LIMIT 1"
        )

        try:
            with database.get_sqla_engine() as engine:
                with engine.connect() as connection:
                    result = connection.execute(query, {"username": username})
                    return result.first() is not None
        except Exception:  # pylint: disable=broad-except
            logger.exception("Unable to verify MoH org-unit level for %r", username)
            return False

    def can_access_moh_dashboard(self, dashboard: Any) -> bool:
        """Return whether the active user may access MoH-restricted dashboards."""
        if dashboard is None:
            return False
        if dashboard.id not in self._level_one_dashboard_ids() or self.is_admin():
            return True

        username = get_current_user()
        return isinstance(username, str) and self._user_has_level_one_org_unit(username)

    def raise_for_access(self, *args: Any, **kwargs: Any) -> None:
        """Deny level-one dashboards before running Superset's RBAC checks."""
        dashboard = kwargs.get("dashboard")
        if dashboard is None and args:
            dashboard = args[0]
        if dashboard is not None and not self.can_access_moh_dashboard(dashboard):
            raise SupersetSecurityException(
                self.get_dashboard_access_error_object(dashboard)
            )
        super().raise_for_access(*args, **kwargs)
