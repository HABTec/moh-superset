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
"""Record what each MoH alert run sent

Adds the details the Usage Dashboard reports on:
  1. moh_alert_delivery            — alert name and period judged by the run
  2. moh_alert_delivery_recipient  — subject, send time, error, rows shown
  3. moh_alert_delivery_facility   — new: one row per flagged facility per run

Revision ID: eae465bae7d4
Revises: c7d8e9f0a1b2
Create Date: 2026-10-28 09:00:00.000000

"""

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from superset.migrations.shared.utils import (
    add_columns,
    create_fks_for_table,
    create_index,
    create_table,
    drop_columns,
    drop_fks_for_table,
    drop_index,
    drop_table,
)

# revision identifiers, used by Alembic.
revision = "eae465bae7d4"
down_revision = "c7d8e9f0a1b2"

DELIVERY_TABLE = "moh_alert_delivery"
RECIPIENT_TABLE = "moh_alert_delivery_recipient"
FACILITY_TABLE = "moh_alert_delivery_facility"


def upgrade():
    add_columns(
        DELIVERY_TABLE,
        Column("alert_name", String(150), nullable=True),
        Column("period", String(32), nullable=True),
    )
    add_columns(
        RECIPIENT_TABLE,
        Column("subject", String(255), nullable=True),
        Column("sent_at", DateTime, nullable=True),
        Column("error_message", Text, nullable=True),
        Column("facilities_shown", Integer, nullable=True),
    )

    create_table(
        FACILITY_TABLE,
        Column("id", Integer, primary_key=True),
        # FK → moh_alert_delivery.id
        Column("delivery_id", Integer, nullable=False),
        Column("org_unit_id", String(32), nullable=False),
        Column("org_unit_name", String(255), nullable=True),
        Column("value", Float, nullable=True),
        Column("period", String(32), nullable=True),
    )
    create_index(
        FACILITY_TABLE,
        "ix_moh_alert_delivery_facility_delivery_id",
        ["delivery_id"],
    )
    create_index(
        FACILITY_TABLE,
        "ix_moh_alert_delivery_facility_org_unit_id",
        ["org_unit_id"],
    )
    create_fks_for_table(
        foreign_key_name="fk_moh_alert_delivery_facility_delivery_id",
        table_name=FACILITY_TABLE,
        referenced_table=DELIVERY_TABLE,
        local_cols=["delivery_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )


def downgrade():
    drop_fks_for_table(
        FACILITY_TABLE,
        ["fk_moh_alert_delivery_facility_delivery_id"],
    )
    drop_index(FACILITY_TABLE, "ix_moh_alert_delivery_facility_org_unit_id")
    drop_index(FACILITY_TABLE, "ix_moh_alert_delivery_facility_delivery_id")
    drop_table(FACILITY_TABLE)

    drop_columns(
        RECIPIENT_TABLE,
        "subject",
        "sent_at",
        "error_message",
        "facilities_shown",
    )
    drop_columns(DELIVERY_TABLE, "alert_name", "period")
