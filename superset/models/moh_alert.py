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
"""MoH Hierarchical Alert Service — SQLAlchemy models.

Three tables supporting the scheduled alert engine:
  - moh_alert                 — alert definition (one row per alert)
  - moh_alert_delivery        — one row per execution run
  - moh_alert_delivery_recipient — one row per recipient per run
"""

import logging

from flask_appbuilder import Model
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from superset.models.helpers import AuditMixinNullable

logger = logging.getLogger(__name__)


# ── Alert definition ────────────────────────────────────────────────
class MohAlert(AuditMixinNullable, Model):
    """One row per alert definition (FR-1, FR-10).

    Columns follow the design spec in Section 6.1 of the detailed
    design document.
    """

    __tablename__ = "moh_alert"

    id = Column(Integer, primary_key=True)
    name = Column(String(150), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True, server_default="1")

    # FK to dbs.id — the ClickHouse connection to evaluate against
    database_id = Column(Integer, ForeignKey("dbs.id"), nullable=False)
    database = relationship(
        "Database",
        foreign_keys=[database_id],
        backref="moh_alerts",
    )

    # Alert condition SQL (must return rows with org_unit_id)
    sql_query = Column(Text, nullable=False)

    # Schedule
    crontab = Column(String(1000), nullable=False)
    timezone = Column(
        String(100), nullable=False, default="Africa/Addis_Ababa"
    )

    # Guards
    grace_period = Column(Integer, nullable=False, default=14400)  # seconds
    working_timeout = Column(Integer, nullable=False, default=120)  # seconds

    # Deep-link target
    dashboard_id = Column(
        Integer, ForeignKey("dashboards.id"), nullable=True, default=3
    )
    dashboard = relationship(
        "Dashboard",
        foreign_keys=[dashboard_id],
        backref="moh_alerts",
    )

    # Email configuration
    subject_template = Column(String(255), nullable=True)

    # Column-role mapping (JSON): facility name col, period col, etc.
    html_extra = Column(Text, nullable=True, default="{}")

    # Last-run status surfaced on the admin list page
    last_run_at = Column(DateTime, nullable=True)
    last_run_status = Column(String(32), nullable=True)
    last_error = Column(Text, nullable=True)

    # Alert owner — notified on failure
    owner_id = Column(Integer, ForeignKey("ab_user.id"), nullable=True)
    owner = relationship(
        "User",
        foreign_keys=[owner_id],
        backref="moh_alerts_owned",
    )

    # ── Relationships ──────────────────────────────────────────────
    deliveries = relationship(
        "MohAlertDelivery",
        back_populates="alert",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_moh_alert_enabled", "enabled"),
        Index("ix_moh_alert_database_id", "database_id"),
    )

    def __repr__(self) -> str:
        return f"<MohAlert {self.name!r} enabled={self.enabled}>"


# ── Delivery (run) audit ───────────────────────────────────────────
class MohAlertDelivery(AuditMixinNullable, Model):
    """One row per execution run (Section 6.2).

    This record doubles as the run lock: its existence with status
    ``started`` prevents duplicate concurrent evaluations.
    """

    __tablename__ = "moh_alert_delivery"

    id = Column(Integer, primary_key=True)
    alert_id = Column(
        Integer, ForeignKey("moh_alert.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id = Column(String(64), nullable=True)

    # Timing
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    # Status: started | success | failed | skipped
    status = Column(String(32), nullable=False, default="started")
    error_message = Column(Text, nullable=True)

    # Counts
    failing_facilities = Column(Integer, nullable=False, default=0)
    ignored_rows = Column(Integer, nullable=False, default=0)
    recipients = Column(Integer, nullable=False, default=0)

    # ── Relationships ──────────────────────────────────────────────
    alert = relationship(
        "MohAlert",
        back_populates="deliveries",
    )
    recipient_rows = relationship(
        "MohAlertDeliveryRecipient",
        back_populates="delivery",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_moh_alert_delivery_alert_id", "alert_id"),
        Index("ix_moh_alert_delivery_status", "status"),
        Index("ix_moh_alert_delivery_started_at", "started_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<MohAlertDelivery alert_id={self.alert_id} "
            f"status={self.status!r}>"
        )


# ── Per-recipient audit ────────────────────────────────────────────
class MohAlertDeliveryRecipient(Model):
    """One row per recipient per run (Section 6.3).

    Records every email sent (or attempted) for accountability.
    """

    __tablename__ = "moh_alert_delivery_recipient"

    id = Column(Integer, primary_key=True)
    delivery_id = Column(
        Integer, ForeignKey("moh_alert_delivery.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Recipient identity
    username = Column(String(150), nullable=True)
    email = Column(String(254), nullable=True)

    # Recipient's own org-unit context
    org_unit_id = Column(String(32), nullable=True)
    org_unit_level = Column(Integer, nullable=True)

    # Scoped failing facility count for this recipient
    facilities = Column(Integer, nullable=False, default=0)

    # SMTP outcome
    sent = Column(Boolean, nullable=False, default=False)

    # ── Relationships ──────────────────────────────────────────────
    delivery = relationship(
        "MohAlertDelivery",
        back_populates="recipient_rows",
    )

    __table_args__ = (
        Index("ix_moh_alert_delivery_recipient_delivery_id", "delivery_id"),
        Index("ix_moh_alert_delivery_recipient_username", "username"),
    )

    def __repr__(self) -> str:
        return (
            f"<MohAlertDeliveryRecipient delivery_id={self.delivery_id} "
            f"email={self.email!r}>"
        )
