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

from flask import current_app, g
from sqlalchemy import text

from superset import db
from superset.exceptions import SupersetSecurityException
from superset.security.manager import SupersetSecurityManager
from superset.tasks.utils import get_current_user
from superset.utils import json

logger = logging.getLogger(__name__)


def _quote_identifier(identifier: str) -> str:
    """Quote a SQL identifier for ClickHouse (backticks)."""
    return "`" + identifier.replace("`", "``") + "`"


class MoHSecurityManager(SupersetSecurityManager):
    """Apply MoH dashboard restrictions before Superset's standard checks."""

    def _level_one_dashboard_ids(self) -> set[int]:
        """Return dashboard IDs whose access is reserved for level-one users."""
        configured_ids = current_app.config.get("MOH_LEVEL_ONE_DASHBOARD_IDS", ())
        if isinstance(configured_ids, str):
            configured_ids = configured_ids.split(",")
        try:
            return {
                int(dashboard_id)
                for dashboard_id in configured_ids
                if str(dashboard_id).strip()
            }
        except (TypeError, ValueError):
            logger.error("MOH_LEVEL_ONE_DASHBOARD_IDS contains an invalid dashboard ID")
            return set()

    def _level_one_org_unit_level(self) -> int:
        """Org-unit level that grants access to restricted dashboards."""
        try:
            return int(current_app.config.get("MOH_LEVEL_ONE_ORG_UNIT_LEVEL", 1))
        except (TypeError, ValueError):
            logger.error("MOH_LEVEL_ONE_ORG_UNIT_LEVEL is invalid; defaulting to 1")
            return 1

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
        required_level = self._level_one_org_unit_level()

        from superset.models.core import Database

        database = (
            db.session.query(Database).filter_by(database_name=database_name).first()
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
            "ON toString(user_org_unit.org_unit_id) = toString(org_unit.id) "
            "WHERE user_org_unit.username = :username "
            "AND org_unit.level = :required_level LIMIT 1"
        )

        try:
            with database.get_sqla_engine() as engine:
                try:
                    with engine.connect() as connection:
                        result = connection.execute(
                            query,
                            {
                                "username": username,
                                "required_level": required_level,
                            },
                        )
                        allowed = result.first() is not None
                        logger.debug(
                            "MoH level check user=%r level=%s allowed=%s",
                            username,
                            required_level,
                            allowed,
                        )
                        return allowed
                finally:
                    # get_sqla_engine() builds a NEW engine per call and never
                    # disposes it, so its sockets to ClickHouse are abandoned and
                    # accumulate in CLOSE-WAIT. Dispose it here; nothing else
                    # shares this engine.
                    engine.dispose()
        except Exception:  # pylint: disable=broad-except
            logger.exception("Unable to verify MoH org-unit level for %r", username)
            return False

    def _dashboard_id_from_access_kwargs(self, kwargs: dict[str, Any]) -> int | None:
        """Resolve a dashboard id from raise_for_access kwargs."""
        dashboard = kwargs.get("dashboard")
        if dashboard is not None and getattr(dashboard, "id", None) is not None:
            try:
                return int(dashboard.id)
            except (TypeError, ValueError):
                return None

        # Chart/data requests usually pass dashboardId in form_data, not dashboard=.
        for key in ("query_context", "viz"):
            obj = kwargs.get(key)
            form_data = getattr(obj, "form_data", None) if obj is not None else None
            if not isinstance(form_data, dict):
                continue
            raw_id = form_data.get("dashboardId")
            if raw_id is None:
                continue
            try:
                return int(raw_id)
            except (TypeError, ValueError):
                return None
        return None

    def _datasource_from_access_kwargs(self, kwargs: dict[str, Any]) -> Any:
        """Return the dataset being read, from the server-side raise_for_access kwargs.

        Unlike dashboardId this is not taken from the request, so a client
        cannot remove it.
        """
        datasource = kwargs.get("datasource")
        for key in ("query_context", "viz", "chart"):
            if datasource is not None:
                break
            obj = kwargs.get(key)
            datasource = getattr(obj, "datasource", None) if obj is not None else None
        if datasource is None or getattr(datasource, "type", "table") != "table":
            return None
        return datasource

    @staticmethod
    def _native_filter_dataset_rows(
        dashboards: list[tuple[int, str | None]],
    ) -> list[tuple[int, int]]:
        """(dashboard id, dataset id) pairs for datasets used by native filters."""
        rows = []
        for dashboard_id, json_metadata in dashboards:
            try:
                filters = (
                    json.loads(json_metadata or "{}").get("native_filter_configuration")
                    or []
                )
            except (TypeError, ValueError, AttributeError):
                continue
            for native_filter in filters:
                for target in native_filter.get("targets") or []:
                    try:
                        rows.append((dashboard_id, int(target["datasetId"])))
                    except (KeyError, TypeError, ValueError):
                        continue
        return rows

    def _level_one_only_dataset_ids(self) -> set[int]:
        """Datasets used by level-one dashboards and by no other dashboard.

        Reading one of these is reading level-one dashboard data, whatever
        dashboardId the request carries. Datasets also shown on other dashboards
        are left to the normal RBAC checks.
        """
        restricted = self._level_one_dashboard_ids()
        if not restricted:
            return set()
        memo_key = "_moh_level_one_datasets"
        if (memo := getattr(g, memo_key, None)) is not None:
            return memo

        ttl = self._level_one_cache_ttl()
        cache_key = "moh_level_one_datasets:" + ",".join(map(str, sorted(restricted)))
        cache = None
        dataset_ids = None
        if ttl > 0:
            try:
                from superset.extensions import cache_manager

                cache = cache_manager.cache
                cached = cache.get(cache_key)
                dataset_ids = set(cached) if cached is not None else None
            except Exception:  # pylint: disable=broad-except
                cache = None
        if dataset_ids is None:
            from superset.models.dashboard import Dashboard, dashboard_slices
            from superset.models.slice import Slice

            try:
                rows = (
                    db.session.query(
                        dashboard_slices.c.dashboard_id, Slice.datasource_id
                    )
                    .join(Slice, Slice.id == dashboard_slices.c.slice_id)
                    .filter(Slice.datasource_type == "table")
                    .all()
                )
                rows += self._native_filter_dataset_rows(
                    db.session.query(Dashboard.id, Dashboard.json_metadata).all()
                )
            except Exception:  # pylint: disable=broad-except
                logger.exception("Unable to resolve MoH level-one datasets")
                return set()
            level_one = {
                ds for dash, ds in rows if dash in restricted and ds is not None
            }
            elsewhere = {ds for dash, ds in rows if dash not in restricted}
            dataset_ids = level_one - elsewhere
            if cache is not None:
                try:
                    cache.set(cache_key, sorted(dataset_ids), timeout=ttl)
                except Exception:  # pylint: disable=broad-except
                    logger.debug(
                        "Could not cache MoH level-one datasets", exc_info=True
                    )
        try:
            setattr(g, memo_key, dataset_ids)
        except RuntimeError:  # outside a request/app context
            pass
        return dataset_ids

    def _slice_id_from_access_kwargs(self, kwargs: dict[str, Any]) -> int | None:
        """Resolve the requested chart id from a chart/data request's form_data."""
        for key in ("query_context", "viz"):
            obj = kwargs.get(key)
            form_data = getattr(obj, "form_data", None) if obj is not None else None
            if not isinstance(form_data, dict) or form_data.get("slice_id") is None:
                continue
            try:
                return int(form_data["slice_id"])
            except (TypeError, ValueError):
                return None
        return None

    def _raise_for_hidden_tab_chart(
        self, dashboard_id: int, kwargs: dict[str, Any]
    ) -> None:
        """Deny data for a chart that sits only in tabs hidden from the user."""
        slice_id = self._slice_id_from_access_kwargs(kwargs)
        if slice_id is None:
            return

        from superset import moh_tab_access
        from superset.models.dashboard import Dashboard

        dashboard = kwargs.get("dashboard") or db.session.get(Dashboard, dashboard_id)
        if dashboard is None:
            return
        if slice_id in moh_tab_access.hidden_chart_ids(dashboard):
            raise SupersetSecurityException(
                self.get_dashboard_access_error_object(dashboard)
            )

    def _level_one_cache_ttl(self) -> int:
        """Seconds to cache a user's level-one verdict. 0 disables caching."""
        try:
            return int(current_app.config.get("MOH_LEVEL_ONE_CACHE_TTL", 300))
        except (TypeError, ValueError):
            return 300

    def _cached_level_one_check(self, username: str) -> bool:
        """Level-one verdict for ``username``, cached.

        raise_for_access() fires many times per chart/dashboard request, and the
        underlying lookup is a cross-database join. Two layers keep it off the
        hot path: a per-request memo collapses the repeats within one request,
        and a short-TTL shared cache collapses them across requests.
        """
        memo = getattr(g, "_moh_level_one_memo", None)
        if memo is None:
            memo = {}
            try:
                g._moh_level_one_memo = memo  # pylint: disable=protected-access
            except RuntimeError:  # outside a request/app context
                memo = None
        if memo is not None and username in memo:
            return memo[username]

        ttl = self._level_one_cache_ttl()
        cache_key = f"moh_level_one:{username}:{self._level_one_org_unit_level()}"
        cache = None
        if ttl > 0:
            try:
                from superset.extensions import cache_manager

                cache = cache_manager.cache
                cached = cache.get(cache_key)
            except Exception:  # pylint: disable=broad-except
                cache, cached = None, None
            if cached is not None:
                allowed = bool(cached)
                if memo is not None:
                    memo[username] = allowed
                return allowed

        allowed = self._user_has_level_one_org_unit(username)
        if memo is not None:
            memo[username] = allowed
        if cache is not None:
            try:
                cache.set(cache_key, allowed, timeout=ttl)
            except Exception:  # pylint: disable=broad-except
                logger.debug("Could not cache MoH level-one verdict", exc_info=True)
        return allowed

    def _level_one_guest_usernames(self) -> set[str]:
        """Guest-token usernames explicitly granted level-one access.

        Distinct from the org-unit table: a guest token's username never has a
        row there, so without this allowlist no guest identity can ever reach a
        level-one dashboard. Empty by default, so this changes nothing until an
        operator opts a specific guest identity in.
        """
        configured = current_app.config.get("MOH_LEVEL_ONE_GUEST_USERNAMES", ())
        if isinstance(configured, str):
            configured = configured.split(",")
        return {str(name).strip() for name in configured if str(name).strip()}

    def user_can_access_level_one_dashboard(self) -> bool:
        """Return whether the current user may open MoH level-one dashboards."""
        if self.is_admin():
            return True
        username = get_current_user()
        if not isinstance(username, str):
            return False
        if username in self._level_one_guest_usernames():
            return True
        return self._cached_level_one_check(username)

    def can_access_moh_dashboard(self, dashboard: Any) -> bool:
        """Return whether the active user may access MoH-restricted dashboards."""
        if dashboard is None:
            return False
        try:
            dashboard_id = int(dashboard.id)
        except (TypeError, ValueError, AttributeError):
            return False
        if dashboard_id not in self._level_one_dashboard_ids():
            return True
        return self.user_can_access_level_one_dashboard()

    def raise_for_access(self, *args: Any, **kwargs: Any) -> None:
        """
        Deny level-one dashboards, their own datasets, and charts in tabs hidden
        from the user (see ``superset.moh_tab_access``) before RBAC checks.
        """
        dashboard_id = self._dashboard_id_from_access_kwargs(kwargs)
        if (
            dashboard_id is not None
            and dashboard_id in self._level_one_dashboard_ids()
            and not self.user_can_access_level_one_dashboard()
        ):
            dashboard = kwargs.get("dashboard")
            if dashboard is None:
                dashboard = type(
                    "Dashboard",
                    (),
                    {"id": dashboard_id, "dashboard_title": ""},
                )()
            raise SupersetSecurityException(
                self.get_dashboard_access_error_object(dashboard)
            )
        datasource = self._datasource_from_access_kwargs(kwargs)
        datasource_id = getattr(datasource, "id", None)
        if (
            datasource_id is not None
            and datasource_id in self._level_one_only_dataset_ids()
            and not self.user_can_access_level_one_dashboard()
        ):
            raise SupersetSecurityException(
                self.get_datasource_access_error_object(datasource)
            )
        if dashboard_id is not None:
            self._raise_for_hidden_tab_chart(dashboard_id, kwargs)
        super().raise_for_access(*args, **kwargs)
