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
"""Celery tasks for the MoH hierarchical alert service.

- ``moh_alert.scheduler`` — runs each minute, dispatches due alerts.
- ``moh_alert.execute`` — evaluates an alert, resolves recipients and sends.

Importing ``sqlalchemy`` models at module level is invalid during config
loading (the encryption factory is not initialized yet), so all model and
``db`` access happens inside functions via the ``_load_*`` helpers.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, TYPE_CHECKING

from celery import Task
from flask import current_app
from sqlalchemy import bindparam, text

from superset.extensions import celery_app
from superset.moh_alerts.connection import get_moh_database
from superset.moh_alerts.deep_link import build_deep_link
from superset.moh_alerts.email_renderer import (
    csv_filename,
    render_alert_csv,
    render_alert_email,
    render_subject,
)
from superset.moh_alerts.recipient_resolver import resolve
from superset.tasks.cron_util import cron_schedule_window
from superset.utils import json

if TYPE_CHECKING:
    from superset.models.core import Database
    from superset.models.moh_alert import (
        MohAlert,
        MohAlertDelivery,
        MohAlertDeliveryFacility,
    )

logger = logging.getLogger(__name__)


def _load_db():
    """Lazy import of the SQLAlchemy db extension."""
    from superset.extensions import db  # pylint: disable=import-outside-toplevel

    return db


def _load_models():
    """Lazy import of the alert models."""
    from superset.models.moh_alert import (  # pylint: disable=import-outside-toplevel
        MohAlert,
        MohAlertDelivery,
        MohAlertDeliveryRecipient,
    )

    return MohAlert, MohAlertDelivery, MohAlertDeliveryRecipient


def _load_facility_model() -> type[MohAlertDeliveryFacility]:
    """Lazy import of the flagged-facility audit model."""
    from superset.models.moh_alert import (  # pylint: disable=import-outside-toplevel
        MohAlertDeliveryFacility,
    )

    return MohAlertDeliveryFacility


def _send_email_smtp(*args, **kwargs):
    from superset.utils.core import (  # pylint: disable=import-outside-toplevel
        send_email_smtp,
    )

    return send_email_smtp(*args, **kwargs)


@celery_app.task(
    name="moh_alert.scheduler",
    bind=True,
)
def scheduler(self: Task) -> None:  # pylint: disable=unused-argument
    """Dispatch due alerts based on their cron schedule."""
    if not current_app.config.get("MOH_ALERTS_ENABLED", False):
        return

    db = _load_db()
    moh_alert_model, _, _ = _load_models()

    try:
        alerts = (
            db.session.query(moh_alert_model)
            .filter(moh_alert_model.enabled.is_(True))
            .all()
        )
    except Exception:  # pylint: disable=broad-except
        logger.exception("moh_alert.scheduler failed to list alerts")
        return

    for alert in alerts:
        for due_at in cron_schedule_window(
            datetime.now(tz=timezone.utc), alert.crontab, alert.timezone
        ):
            logger.info("Scheduling moh alert %s eta: %s", alert.name, due_at)
            execute.apply_async((alert.id,), eta=due_at)


def _is_recent_success(alert_id: int, grace: int) -> bool:
    """True if a run for the alert succeeded recently enough to skip."""
    if grace <= 0:
        return False
    _, delivery_model, _ = _load_models()
    db = _load_db()
    cutoff = datetime.now(tz=timezone.utc).replace(tzinfo=None) - timedelta(
        seconds=grace
    )
    return (
        db.session.query(delivery_model.id)
        .filter(
            delivery_model.alert_id == alert_id,
            delivery_model.status.in_(["started", "success"]),
            delivery_model.started_at >= cutoff,
        )
        .first()
        is not None
    )


@celery_app.task(
    name="moh_alert.execute",
    bind=True,
    soft_time_limit=600,
    time_limit=900,
)
def execute(self: Task, alert_id: int) -> None:  # pylint: disable=unused-argument
    """Evaluate one alert, resolve recipients and send emails."""
    db = _load_db()
    moh_alert_model, delivery_model, _ = _load_models()

    alert = db.session.get(moh_alert_model, alert_id)
    if alert is None or not alert.enabled:
        return

    grace = (
        alert.grace_period
        if alert.grace_period is not None
        else current_app.config.get("MOH_ALERTS_DEFAULT_GRACE_PERIOD", 14400)
    )
    if _is_recent_success(alert.id, grace):
        _log_skipped(alert)
        return

    delivery = delivery_model(
        alert_id=alert.id,
        task_id=self.request.id,
        scheduled_at=datetime.now(tz=timezone.utc).replace(tzinfo=None),
        started_at=datetime.now(tz=timezone.utc).replace(tzinfo=None),
        status="started",
    )
    db.session.add(delivery)
    db.session.commit()

    try:
        _run_delivery(alert, delivery)
    except Exception as ex:  # pylint: disable=broad-except
        db.session.rollback()
        delivery.status = "failed"
        delivery.error_message = f"{type(ex).__name__}: {ex}"
        delivery.finished_at = datetime.now(tz=timezone.utc).replace(tzinfo=None)
        alert.last_run_status = "failed"
        alert.last_error = delivery.error_message
        db.session.commit()
        logger.exception("moh alert %s failed", alert_id)
        _notify_owners_on_failure(alert, delivery.error_message)
        raise


def _log_skipped(alert: MohAlert) -> None:
    db = _load_db()
    _, delivery_model, _ = _load_models()
    db.session.add(
        delivery_model(
            alert_id=alert.id,
            scheduled_at=datetime.now(tz=timezone.utc).replace(tzinfo=None),
            started_at=datetime.now(tz=timezone.utc).replace(tzinfo=None),
            finished_at=datetime.now(tz=timezone.utc).replace(tzinfo=None),
            status="skipped",
        )
    )
    db.session.commit()


def _run_delivery(alert: MohAlert, delivery: MohAlertDelivery) -> None:
    db = _load_db()
    _, _, recipient_model = _load_models()

    database = get_moh_database(alert.database_id)

    rows = _evaluate(alert, database)

    valid = [r for r in rows if r.get("org_unit_id")]
    ignored = len(rows) - len(valid)

    # de-duplicate by facility keeping the first row
    seen: dict[str, Any] = {}
    for r in valid:
        seen.setdefault(str(r["org_unit_id"]), r)

    schema = current_app.config.get("MOH_ORG_UNITS_SCHEMA", "moh")
    org_units_table = current_app.config.get("MOH_ORG_UNITS_TABLE", "org_units")
    user_org_units_table = current_app.config.get(
        "MOH_USER_ORG_UNITS_TABLE", "dim_user_orgunit"
    )
    max_per_query = current_app.config.get("MOH_ALERTS_MAX_FACILITIES_PER_QUERY", 5000)
    max_recipients = current_app.config.get("MOH_ALERTS_MAX_RECIPIENTS", 2000)
    email_cap = current_app.config.get("MOH_ALERTS_EMAIL_CAP", 50)
    attach_csv = current_app.config.get("MOH_ALERTS_ATTACH_CSV", True)

    per_user, resolver_ignored = resolve(
        database,
        seen.keys(),
        schema=schema,
        org_units_table=org_units_table,
        user_org_units_table=user_org_units_table,
        max_per_query=max_per_query,
    )
    ignored += resolver_ignored

    extra = _load_extra(alert)
    facility_model = _load_facility_model()
    records = facility_records(seen, extra)
    delivery.alert_name = alert.name
    delivery.period = next((r["period"] for r in records if r["period"]), None)
    db.session.add_all(
        facility_model(delivery_id=delivery.id, **record) for record in records
    )

    emails = _emails_for_usernames(per_user.keys())

    sent_count = 0
    for username, facilities in per_user.items():
        if sent_count >= max_recipients:
            logger.warning(
                "moh alert %s: recipient cap (%s) reached", alert.id, max_recipients
            )
            break
        email = emails.get(username)
        if not email:
            continue
        subset = [seen[f] for f in facilities if f in seen]
        if not subset:
            continue

        user_org_unit, user_level = _user_org_context(
            database, username, schema, user_org_units_table, org_units_table
        )
        deep_link = build_deep_link(alert, user_org_unit) if user_org_unit else None
        subject = render_subject(alert, extra, subset)
        # Lists longer than the email table travel in full as a CSV attachment
        attached = attach_csv and len(subset) > email_cap
        attachments = (
            {csv_filename(alert.name, delivery.period): render_alert_csv(extra, subset)}
            if attached
            else {}
        )
        body = render_alert_email(
            alert, extra, subset, deep_link, email_cap=email_cap, attached=attached
        )
        sent = False
        sent_at = None
        error_message = None
        try:
            _send_email_smtp(
                to=email,
                subject=subject,
                html_content=body,
                config=current_app.config,
                data=attachments,
                images={},
            )
            sent = True
            sent_at = datetime.now(tz=timezone.utc).replace(tzinfo=None)
            sent_count += 1
        except Exception as ex:  # pylint: disable=broad-except
            error_message = f"{type(ex).__name__}: {ex}"[:1000]
            logger.warning(
                "moh alert %s: email to %s (%s) failed: %s",
                alert.id,
                username,
                email,
                ex,
            )
        db.session.add(
            recipient_model(
                delivery_id=delivery.id,
                username=username,
                email=email,
                org_unit_id=user_org_unit,
                org_unit_level=user_level,
                facilities=len(subset),
                facilities_shown=min(len(subset), email_cap),
                subject=subject[:255],
                sent=sent,
                sent_at=sent_at,
                error_message=error_message,
            )
        )

    delivery.status = "success"
    delivery.finished_at = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    delivery.failing_facilities = len(seen)
    delivery.ignored_rows = ignored
    delivery.recipients = sent_count
    alert.last_run_at = delivery.finished_at
    alert.last_run_status = "success"
    alert.last_error = None
    db.session.commit()

    logger.info(
        "moh alert %s success: %s facilities, %s recipients",
        alert.id,
        len(seen),
        sent_count,
    )


def _evaluate(alert: MohAlert, database: Database) -> list[Any]:
    with database.get_sqla_engine() as engine:
        with engine.connect() as conn:
            result = conn.execute(text(alert.sql_query))
            return [dict(row) for row in result.mappings()]


def _emails_for_usernames(usernames: Any) -> dict[str, str]:
    names = [str(u) for u in usernames]
    if not names:
        return {}
    db = _load_db()
    sql = text(
        "SELECT username, email FROM ab_user "
        "WHERE username IN :u AND email IS NOT NULL AND email <> ''"
    ).bindparams(bindparam("u", expanding=True))
    rows = db.session.execute(sql, {"u": names}).mappings()
    return {
        str(r["username"]): str(r["email"])
        for r in rows
        if not _is_reserved_test_email(str(r["email"]))
    }


def _is_reserved_test_email(email: str) -> bool:
    """True for RFC-2606 reserved-domain addresses (e.g. *@example.com).

    Real SMTP servers reject these with a 5xx refusal; skipping them keeps a
    single invalid recipient from blocking the rest of a delivery.
    """
    domain = email.rsplit("@", 1)[-1].lower().strip()
    return domain in {
        "example.com",
        "example.org",
        "example.net",
        "example.edu",
        "invalid",
        "localhost",
    }


def _user_org_context(
    database: Database,
    username: str,
    schema: str,
    user_org_units_table: str = "dim_user_orgunit",
    org_units_table: str = "org_units",
) -> tuple[str | None, int | None]:
    """Best-effort lookup of a user's own org unit and its level."""
    user_table = f"`{schema}`.`{user_org_units_table}`"
    units_table = f"`{schema}`.`{org_units_table}`"
    try:
        with database.get_sqla_engine() as engine:
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        f"SELECT m.org_unit_id AS org_unit_id, o.level AS level "  # noqa: S608 - config-quoted tables, values bound
                        f"FROM {user_table} AS m "
                        f"LEFT JOIN {units_table} AS o ON o.id = m.org_unit_id "
                        "WHERE m.username = :u LIMIT 1"
                    ),
                    {"u": username},
                ).mappings()
                for r in rows:
                    # ClickHouse fills unmatched LEFT JOIN columns with 0
                    level = r.get("level") or None
                    return str(r["org_unit_id"]), int(level) if level else None
    except Exception:  # pylint: disable=broad-except
        logger.debug("org context lookup failed for %s", username, exc_info=True)
    return None, None


def facility_records(
    seen: dict[str, Any], extra: dict[str, Any]
) -> list[dict[str, Any]]:
    """Build one audit record per failing facility from the alert rows.

    ``seen`` maps facility id to its alert row. The metric is the first of
    ``html_extra.metric_cols`` the rows contain (``value`` by default).
    """
    name_col = extra.get("facility_name_col", "org_unit_name")
    period_col = extra.get("period_col", "period")
    metric_cols = extra.get("metric_cols") or ["value"]
    metric_col = next(
        (c for c in metric_cols if any(c in row for row in seen.values())),
        "value",
    )
    records = []
    for org_unit_id, row in seen.items():
        name = row.get(name_col)
        period = row.get(period_col)
        records.append(
            {
                "org_unit_id": str(org_unit_id)[:32],
                "org_unit_name": str(name)[:255] if name is not None else None,
                "value": _to_float(row.get(metric_col)),
                "period": str(period)[:32] if period is not None else None,
            }
        )
    return records


def _to_float(value: Any) -> float | None:
    """Return ``value`` as a float, or None when it is missing or not numeric."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_extra(alert: MohAlert) -> dict[str, Any]:
    try:
        return json.loads(alert.html_extra or "{}")
    except json.JSONDecodeError:
        logger.warning("alert %s html_extra not valid JSON", alert.id)
        return {}


def _notify_owners_on_failure(alert: MohAlert, error: str) -> None:
    recipients: set[str] = set()
    if alert.owner and alert.owner.email:
        recipients.add(alert.owner.email)
    recipients.update(current_app.config.get("AUTH_ADMIN_EMAILS", []))
    if not recipients:
        return
    try:
        _send_email_smtp(
            to=", ".join(sorted(recipients)),
            subject=f"[MoH Alert] {alert.name} failed",
            html_content=(
                f"<p>The MoH alert <b>{alert.name}</b> failed.</p><pre>{error}</pre>"
            ),
            config=current_app.config,
            images={},
        )
    except Exception:  # pylint: disable=broad-except
        logger.exception("failed to notify owners of alert %s", alert.id)
