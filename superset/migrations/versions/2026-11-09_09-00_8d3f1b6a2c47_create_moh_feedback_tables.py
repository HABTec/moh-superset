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
"""Create the MoH feedback tables

  1. moh_feedback        — one row per item of feedback
  2. moh_feedback_event  — append-only history of each item

Revision ID: 8d3f1b6a2c47
Revises: eae465bae7d4
Create Date: 2026-11-09 09:00:00.000000

"""

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy_utils import UUIDType

from superset.migrations.shared.utils import (
    create_fks_for_table,
    create_index,
    create_table,
    drop_fks_for_table,
    drop_index,
    drop_table,
)

# revision identifiers, used by Alembic.
revision = "8d3f1b6a2c47"
down_revision = "eae465bae7d4"

FEEDBACK_TABLE = "moh_feedback"
EVENT_TABLE = "moh_feedback_event"
USER_TABLE = "ab_user"


def upgrade():
    create_table(
        FEEDBACK_TABLE,
        Column("id", Integer, primary_key=True),
        Column("uuid", UUIDType(binary=True), nullable=True),
        Column("submission_id", String(64), nullable=False),
        # FK → ab_user.id
        Column("created_by_fk", Integer, nullable=True),
        Column("sender_name", String(255), nullable=False),
        Column("sender_email", String(320), nullable=True),
        Column("sender_role", String(255), nullable=True),
        Column("origin_unit_id", String(32), nullable=True),
        Column("origin_path", Text, nullable=True),
        Column("origin_level1id", String(32), nullable=True),
        Column("origin_level2id", String(32), nullable=True),
        Column("origin_level3id", String(32), nullable=True),
        Column("origin_level4id", String(32), nullable=True),
        Column("origin_level5id", String(32), nullable=True),
        Column("origin_level6id", String(32), nullable=True),
        Column("origin_level7id", String(32), nullable=True),
        Column("type", String(20), nullable=False),
        Column("message", Text, nullable=False),
        Column("page_url", String(2048), nullable=True),
        Column("status", String(20), nullable=False, server_default="new"),
        Column("created_on", DateTime, nullable=False),
        Column("changed_on", DateTime, nullable=False),
    )
    create_index(FEEDBACK_TABLE, "uq_moh_feedback_uuid", ["uuid"], unique=True)
    create_index(
        FEEDBACK_TABLE,
        "uq_moh_feedback_submission_id",
        ["submission_id"],
        unique=True,
    )
    create_index(
        FEEDBACK_TABLE,
        "ix_moh_feedback_created_by_created_on",
        ["created_by_fk", "created_on"],
    )
    create_fks_for_table(
        foreign_key_name="fk_moh_feedback_created_by_fk",
        table_name=FEEDBACK_TABLE,
        referenced_table=USER_TABLE,
        local_cols=["created_by_fk"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )

    create_table(
        EVENT_TABLE,
        Column("id", Integer, primary_key=True),
        # FK → moh_feedback.id
        Column("feedback_id", Integer, nullable=False),
        Column("event_type", String(30), nullable=False),
        Column("from_status", String(20), nullable=True),
        Column("to_status", String(20), nullable=True),
        # FK → ab_user.id
        Column("user_id", Integer, nullable=True),
        Column("actor_name", String(255), nullable=True),
        Column("message", Text, nullable=True),
        Column("created_on", DateTime, nullable=False),
    )
    create_index(EVENT_TABLE, "ix_moh_feedback_event_feedback_id", ["feedback_id"])
    create_fks_for_table(
        foreign_key_name="fk_moh_feedback_event_feedback_id",
        table_name=EVENT_TABLE,
        referenced_table=FEEDBACK_TABLE,
        local_cols=["feedback_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )
    create_fks_for_table(
        foreign_key_name="fk_moh_feedback_event_user_id",
        table_name=EVENT_TABLE,
        referenced_table=USER_TABLE,
        local_cols=["user_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )


def downgrade():
    drop_fks_for_table(
        EVENT_TABLE,
        ["fk_moh_feedback_event_user_id", "fk_moh_feedback_event_feedback_id"],
    )
    drop_index(EVENT_TABLE, "ix_moh_feedback_event_feedback_id")
    drop_table(EVENT_TABLE)

    drop_fks_for_table(FEEDBACK_TABLE, ["fk_moh_feedback_created_by_fk"])
    drop_index(FEEDBACK_TABLE, "ix_moh_feedback_created_by_created_on")
    drop_index(FEEDBACK_TABLE, "uq_moh_feedback_submission_id")
    drop_index(FEEDBACK_TABLE, "uq_moh_feedback_uuid")
    drop_table(FEEDBACK_TABLE)
