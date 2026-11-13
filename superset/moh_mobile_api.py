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
"""MoH API for mobile clients, authenticated with a Bearer token.

Mirrors the read-only endpoints of ``superset.moh_orgunits_api`` under
``/api/v1/moh/mobile``. Those endpoints accept only the browser session
cookie; these accept the same access token as the standard Superset REST API:

1. ``POST /api/v1/security/login`` with
   ``{"username", "password", "provider": "db", "refresh": true}`` returns
   ``access_token`` and, because of ``"refresh": true``, ``refresh_token``.
2. Every request here sends ``Authorization: Bearer <access_token>``.
3. ``POST /api/v1/security/refresh`` with
   ``Authorization: Bearer <refresh_token>`` returns a new access token.

The token's user becomes the request's user, so org-unit scoping and every
other rule of the original endpoints apply unchanged.

Registered with Flask via the BLUEPRINTS list in ``superset_config.py``.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, g, jsonify, request, Response
from flask_jwt_extended import current_user as jwt_user, verify_jwt_in_request

from superset import moh_orgunits_api as orgunits
from superset.utils import json

logger = logging.getLogger(__name__)

moh_mobile_bp = Blueprint(
    "moh_mobile",
    __name__,
    url_prefix="/api/v1/moh/mobile",
)


def _unauthorized(message: str) -> tuple[Response, int]:
    return jsonify({"message": message}), 401


@moh_mobile_bp.before_request
def _authenticate_bearer() -> tuple[Response, int] | None:
    """Make the Bearer token's user the current user for this request."""
    try:
        verify_jwt_in_request(locations=["headers"])
        user: Any = jwt_user
        user = user._get_current_object() if user is not None else None
    except Exception as ex:  # pylint: disable=broad-except
        logger.info("Mobile API token rejected: %s", type(ex).__name__)
        return _unauthorized("Invalid or missing Bearer token")
    if user is None or not getattr(user, "is_active", False):
        return _unauthorized("User not found or inactive")
    # flask_login reads the request's user from g._login_user, so code using
    # current_user (and Superset's g.user) sees the token's user.
    g._login_user = user  # pylint: disable=protected-access
    g.user = user
    # Drop any org unit memoized for an earlier identity in this request.
    g.pop("moh_assigned_org_unit", None)
    return None


@moh_mobile_bp.route("/organisationUnits", methods=["GET"])
def list_units() -> Any:
    """Same as ``GET /api/v1/moh/dhis2/organisationUnits``."""
    return orgunits.list_units()


@moh_mobile_bp.route("/organisationUnits/<uid>", methods=["GET"])
def get_unit(uid: str) -> Any:
    """Same as ``GET /api/v1/moh/dhis2/organisationUnits/<uid>``."""
    return orgunits.get_unit(uid)


@moh_mobile_bp.route("/me/organisationUnit", methods=["GET"])
def get_my_unit() -> Any:
    """Same as ``GET /api/v1/moh/dhis2/me/organisationUnit``."""
    return orgunits.get_my_unit()


@moh_mobile_bp.route("/latest-period", methods=["GET"])
def get_latest_period() -> Any:
    """Same as ``GET /api/v1/moh/dhis2/latest-period``."""
    return orgunits.get_latest_period()


@moh_mobile_bp.route("/data-freshness", methods=["GET"])
def get_data_freshness() -> Any:
    """Same as ``GET /api/v1/moh/dhis2/data-freshness``."""
    return orgunits.get_data_freshness()


@moh_mobile_bp.route("/tab-context", methods=["GET"])
def get_tab_context() -> Any:
    """Same as ``GET /api/v1/moh/dhis2/tab-context`` (``q`` is JSON).

    A list or object ``dashboardId`` is answered with 400 here, as the shared
    tab lookup needs a hashable id.
    """
    try:
        payload = json.loads(request.args.get("q") or "{}")
    except ValueError:
        payload = None  # the original endpoint answers 400
    if isinstance(payload, dict) and isinstance(
        payload.get("dashboardId"), (list, dict)
    ):
        return jsonify({"message": "dashboardId must be a number or string"}), 400
    return orgunits.get_tab_context()
