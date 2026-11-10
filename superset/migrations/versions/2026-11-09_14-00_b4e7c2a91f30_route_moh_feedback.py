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
"""Route MoH feedback up or down the org-unit tree

Adds to moh_feedback the direction and the unit it was sent to, adds the units
an event moved between, and creates moh_feedback_unit_access.

Revision ID: b4e7c2a91f30
Revises: 8d3f1b6a2c47
Create Date: 2026-11-09 14:00:00.000000

"""

from alembic import op
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, text

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
revision = "b4e7c2a91f30"
down_revision = "8d3f1b6a2c47"

FEEDBACK_TABLE = "moh_feedback"
EVENT_TABLE = "moh_feedback_event"
ACCESS_TABLE = "moh_feedback_unit_access"
CURRENT_INDEX = "uq_moh_feedback_unit_access_current"


def upgrade():
    add_columns(
        FEEDBACK_TABLE,
        Column("direction", String(10), nullable=False, server_default="up"),
        Column("target_unit_id", String(32), nullable=True),
        Column("target_unit_name", String(255), nullable=True),
        Column("target_path", Text, nullable=True),
    )
    add_columns(
        EVENT_TABLE,
        Column("from_unit_id", String(32), nullable=True),
        Column("to_unit_id", String(32), nullable=True),
    )

    create_table(
        ACCESS_TABLE,
        Column("id", Integer, primary_key=True),
        # FK → moh_feedback.id
        Column("feedback_id", Integer, nullable=False),
        Column("unit_id", String(32), nullable=False),
        Column("unit_name", String(255), nullable=True),
        Column("reason", String(20), nullable=False),
        Column("is_current", Boolean, nullable=False),
        Column("granted_on", DateTime, nullable=False),
    )
    create_index(ACCESS_TABLE, "ix_moh_feedback_unit_access_unit_id", ["unit_id"])
    # One responsible unit per item; the shared helper has no partial-index option
    op.create_index(
        CURRENT_INDEX,
        ACCESS_TABLE,
        ["feedback_id"],
        unique=True,
        postgresql_where=text("is_current"),
        sqlite_where=text("is_current = 1"),
    )
    create_fks_for_table(
        foreign_key_name="fk_moh_feedback_unit_access_feedback_id",
        table_name=ACCESS_TABLE,
        referenced_table=FEEDBACK_TABLE,
        local_cols=["feedback_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )


def downgrade():
    drop_fks_for_table(ACCESS_TABLE, ["fk_moh_feedback_unit_access_feedback_id"])
    drop_index(ACCESS_TABLE, CURRENT_INDEX)
    drop_index(ACCESS_TABLE, "ix_moh_feedback_unit_access_unit_id")
    drop_table(ACCESS_TABLE)

    drop_columns(EVENT_TABLE, "from_unit_id", "to_unit_id")
    drop_columns(
        FEEDBACK_TABLE,
        "direction",
        "target_unit_id",
        "target_unit_name",
        "target_path",
    )
