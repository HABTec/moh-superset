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
from __future__ import annotations

import dataclasses
import functools
import logging
import typing
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, cast

from flask import (
    Flask,
    request,
    Response,
)
from flask_wtf.csrf import CSRFError
from sqlalchemy import exc
from werkzeug.exceptions import HTTPException

from superset.commands.exceptions import CommandException, CommandInvalidError
from superset.errors import ErrorLevel, SupersetError, SupersetErrorType
from superset.exceptions import (
    SupersetErrorException,
    SupersetErrorsException,
    SupersetException,
    SupersetSecurityException,
)
from superset.superset_typing import FlaskResponse
from superset.utils import core as utils, json
from superset.utils.log import get_logger_from_status
from superset.views.utils import redirect_to_login

if typing.TYPE_CHECKING:
    from superset.views.base import BaseSupersetView


logger = logging.getLogger(__name__)

JSON_MIMETYPE = "application/json; charset=utf-8"

# Content of the shared HTML error page, per kind of failure
ERROR_PAGES: dict[str, dict[str, Any]] = {
    "database": {
        "label": "Database error",
        "title": "We can't reach the database right now",
        "message": "The portal could not connect to or read from its database. "
        "Your data is safe; this is usually temporary.",
        "hints": [
            "Wait a minute and try again.",
            "If the problem continues, the database server may be down "
            "or under maintenance.",
        ],
        "retry": True,
        "status": 503,
    },
    "server": {
        "label": "Server error",
        "title": "Something went wrong on our side",
        "message": "The server ran into an unexpected problem while handling "
        "your request.",
        "hints": [
            "Try again in a moment.",
            "If you were saving changes, check whether they were saved "
            "before repeating them.",
        ],
        "retry": True,
        "status": 500,
    },
    "timeout": {
        "label": "Timeout",
        "title": "The request took too long",
        "message": "The server did not finish in time. Large dashboards or "
        "busy periods can cause this.",
        "hints": [
            "Try again in a moment.",
            "Narrow the filters (e.g. a shorter period or fewer regions).",
        ],
        "retry": True,
        "status": 504,
    },
    "forbidden": {
        "label": "Access denied",
        "title": "You don't have access to this page",
        "message": "Your account does not have permission to view this resource.",
        "hints": [
            "Check that you are signed in with the right account.",
            "Ask the system administrator to grant you access.",
        ],
        "retry": False,
        "status": 403,
    },
    "not_found": {
        "label": "Not found",
        "title": "We couldn't find that page",
        "message": "The page you are looking for does not exist, was moved, "
        "or was deleted.",
        "hints": [
            "Check the address for typos.",
            "Use the home page to find the dashboard or report.",
        ],
        "retry": False,
        "status": 404,
    },
}

DATABASE_ERROR_TYPES = {
    error_type
    for error_type in SupersetErrorType
    if error_type.name.startswith("CONNECTION_")
    or error_type
    in {
        SupersetErrorType.GENERIC_DB_ENGINE_ERROR,
        SupersetErrorType.DATABASE_NOT_FOUND_ERROR,
    }
}


def wants_html() -> bool:
    """
    True for browser page loads. API calls and fetches from the frontend keep
    getting JSON errors, so they can still show inline error messages.
    """
    if request.path.startswith("/api/"):
        return False
    accept = request.accept_mimetypes
    return (
        accept.accept_html
        and accept.best_match(["application/json", "text/html"]) == "text/html"
    )


def error_kind_from_status(status: int | None) -> str:
    """Map an HTTP status code to an error page kind."""
    if status in {401, 403}:
        return "forbidden"
    if status in {404, 410}:
        return "not_found"
    if status in {408, 504}:
        return "timeout"
    if status == 503:
        return "database"
    return "server"


def error_kind_from_exception(ex: BaseException) -> str:
    """Pick the error page kind that best describes an exception."""
    if isinstance(ex, (exc.OperationalError, exc.InterfaceError, exc.TimeoutError)):
        return "database"
    if isinstance(ex, exc.DBAPIError):
        return "database"
    if isinstance(ex, (SupersetErrorException, SupersetErrorsException)):
        errors = [ex.error] if isinstance(ex, SupersetErrorException) else ex.errors
        if any(error.error_type in DATABASE_ERROR_TYPES for error in errors):
            return "database"
        if any(
            error.error_type == SupersetErrorType.BACKEND_TIMEOUT_ERROR
            for error in errors
        ):
            return "timeout"
        return error_kind_from_status(ex.status)
    if isinstance(ex, HTTPException):
        return error_kind_from_status(ex.code)
    if isinstance(ex, (SupersetException, CommandException)):
        return error_kind_from_status(ex.status)
    return "server"


def html_error_response(app: Flask, kind: str) -> FlaskResponse | None:
    """
    Render the shared error page. The template is rendered straight from the
    Jinja environment, skipping context processors, so that it works even
    when the metadata database is down. Returns None if rendering fails, so
    callers can fall back to JSON.
    """
    page = ERROR_PAGES.get(kind, ERROR_PAGES["server"])
    ref = uuid.uuid4().hex[:12]
    logger.warning("Error page shown: kind=%s ref=%s path=%s", kind, ref, request.path)
    try:
        html = app.jinja_env.get_template("superset/error.html").render(
            kind=kind,
            code=page["status"],
            label=page["label"],
            title=page["title"],
            message=page["message"],
            hints=page["hints"],
            retry=page["retry"],
            ref=ref,
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        )
    except Exception:  # pylint: disable=broad-except
        logger.exception("Failed to render error page")
        return None
    return Response(
        html,
        status=page["status"],
        mimetype="text/html",
        headers={"Cache-Control": "no-store"},
    )


def get_error_level_from_status(
    status_code: int,
) -> ErrorLevel:
    if status_code < 400:
        return ErrorLevel.INFO
    if status_code < 500:
        return ErrorLevel.WARNING
    return ErrorLevel.ERROR


def json_error_response(
    error_details: str | SupersetError | list[SupersetError] | None = None,
    status: int = 500,
    payload: dict[str, Any] | None = None,
) -> FlaskResponse:
    payload = payload or {}

    if isinstance(error_details, list):
        payload["errors"] = [dataclasses.asdict(error) for error in error_details]
    elif isinstance(error_details, SupersetError):
        payload["errors"] = [dataclasses.asdict(error_details)]
    elif isinstance(error_details, str):
        payload["error"] = error_details

    return Response(
        json.dumps(payload, default=json.json_iso_dttm_ser, ignore_nan=True),
        status=status,
        mimetype=JSON_MIMETYPE,
    )


def handle_api_exception(
    f: Callable[..., FlaskResponse],
) -> Callable[..., FlaskResponse]:
    """
    A decorator to catch superset exceptions. Use it after the @api decorator above
    so superset exception handler is triggered before the handler for generic
    exceptions.
    """

    def wraps(self: BaseSupersetView, *args: Any, **kwargs: Any) -> FlaskResponse:
        try:
            return f(self, *args, **kwargs)
        except SupersetSecurityException as ex:
            logger.warning("SupersetSecurityException", exc_info=True)
            return json_error_response([ex.error], status=ex.status, payload=ex.payload)
        except SupersetErrorsException as ex:
            logger.warning(ex, exc_info=True)
            return json_error_response(ex.errors, status=ex.status)
        except SupersetErrorException as ex:
            logger.warning("SupersetErrorException", exc_info=True)
            return json_error_response([ex.error], status=ex.status)
        except SupersetException as ex:
            logger_func, _ = get_logger_from_status(ex.status)
            logger_func(ex.message, exc_info=True)
            return json_error_response(
                utils.error_msg_from_exception(ex), status=ex.status
            )
        except HTTPException as ex:
            logger.exception(ex)
            return json_error_response(
                utils.error_msg_from_exception(ex), status=cast(int, ex.code)
            )
        except (exc.IntegrityError, exc.DatabaseError, exc.DataError) as ex:
            logger.exception(ex)
            return json_error_response(utils.error_msg_from_exception(ex), status=422)
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception(ex)
            return json_error_response(utils.error_msg_from_exception(ex))

    return functools.update_wrapper(wraps, f)


def set_app_error_handlers(app: Flask) -> None:  # noqa: C901
    """
    Set up error handlers for the Flask app
    Refer to SIP-40 and SIP-41 for more details on the error handling strategy
    """

    @app.errorhandler(SupersetErrorException)
    def show_superset_error(ex: SupersetErrorException) -> FlaskResponse:
        logger.warning("SupersetErrorException", exc_info=True)
        if wants_html() and not app.config["DEBUG"]:
            if page := html_error_response(app, error_kind_from_exception(ex)):
                return page
        return json_error_response([ex.error], status=ex.status)

    @app.errorhandler(SupersetErrorsException)
    def show_superset_errors(ex: SupersetErrorsException) -> FlaskResponse:
        logger.warning("SupersetErrorsException", exc_info=True)
        if wants_html() and not app.config["DEBUG"]:
            if page := html_error_response(app, error_kind_from_exception(ex)):
                return page
        return json_error_response(ex.errors, status=ex.status)

    @app.errorhandler(CSRFError)
    def refresh_csrf_token(ex: CSRFError) -> FlaskResponse:
        """Redirect to login if the CSRF token is expired"""
        logger.warning("Refresh CSRF token error", exc_info=True)

        if request.is_json:
            return show_http_exception(ex)

        return redirect_to_login()

    @app.errorhandler(HTTPException)
    def show_http_exception(ex: HTTPException) -> FlaskResponse:
        logger.warning("HTTPException", exc_info=True)

        if (
            wants_html()
            and not app.config["DEBUG"]
            and ex.code in {403, 404, 408, 410, 500, 502, 503, 504}
        ):
            if page := html_error_response(app, error_kind_from_exception(ex)):
                return page

        return json_error_response(
            [
                SupersetError(
                    message=utils.error_msg_from_exception(ex),
                    error_type=SupersetErrorType.GENERIC_BACKEND_ERROR,
                    level=ErrorLevel.ERROR,
                ),
            ],
            status=ex.code or 500,
        )

    @app.errorhandler(CommandException)
    def show_command_errors(ex: CommandException) -> FlaskResponse:
        """
        Temporary handler for CommandException; if an API raises a
        CommandException it should be fixed to map it to SupersetErrorException
        or SupersetErrorsException, with a specific status code and error type
        """
        logger.warning("CommandException", exc_info=True)

        if wants_html() and not app.config["DEBUG"]:
            if page := html_error_response(app, error_kind_from_exception(ex)):
                return page

        extra = ex.normalized_messages() if isinstance(ex, CommandInvalidError) else {}
        return json_error_response(
            [
                SupersetError(
                    message=ex.message,
                    error_type=SupersetErrorType.GENERIC_COMMAND_ERROR,
                    level=get_error_level_from_status(ex.status),
                    extra=extra,
                ),
            ],
            status=ex.status,
        )

    @app.errorhandler(Exception)
    @app.errorhandler(500)
    def show_unexpected_exception(ex: Exception) -> FlaskResponse:
        """Catch-all, to ensure all errors from the backend conform to SIP-40"""
        logger.warning("Exception", exc_info=True)
        logger.exception(ex)

        if wants_html() and not app.config["DEBUG"]:
            if page := html_error_response(app, error_kind_from_exception(ex)):
                return page

        return json_error_response(
            [
                SupersetError(
                    message=utils.error_msg_from_exception(ex),
                    error_type=SupersetErrorType.GENERIC_BACKEND_ERROR,
                    level=ErrorLevel.ERROR,
                ),
            ],
        )
