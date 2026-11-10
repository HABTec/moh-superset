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
"""Queue the emails of the MoH feedback loop

Creates moh_feedback_notification, so an email outlives a mail outage.

Revision ID: d5b2e9c40a17
Revises: a3d6f0b8e714
Create Date: 2026-11-09 23:30:00.000000

"""

from sqlalchemy import Column, DateTime, Integer, String, Text

from superset.migrations.shared.utils import (
    create_fks_for_table,
    create_index,
    create_table,
    drop_fks_for_table,
    drop_index,
    drop_table,
)

# revision identifiers, used by Alembic.
revision = "d5b2e9c40a17"
down_revision = "a3d6f0b8e714"

TABLE = "moh_feedback_notification"
DUE_INDEX = "ix_moh_feedback_notification_status_next"
DEDUPE_INDEX = "uq_moh_feedback_notification_dedupe"
FEEDBACK_FK = "fk_moh_feedback_notification_feedback_id"
USER_FK = "fk_moh_feedback_notification_user_id"


def upgrade():
    create_table(
        TABLE,
        Column("id", Integer, primary_key=True),
        # FK → moh_feedback.id
        Column("feedback_id", Integer, nullable=True),
        # FK → ab_user.id
        Column("user_id", Integer, nullable=True),
        Column("unit_id", String(32), nullable=True),
        Column("exclude_user_id", Integer, nullable=True),
        Column("kind", String(30), nullable=False),
        Column("actor_name", String(255), nullable=True),
        Column("detail", Text, nullable=True),
        Column("dedupe_key", String(120), nullable=True),
        Column("status", String(10), nullable=False),
        Column("attempts", Integer, nullable=False, server_default="0"),
        Column("next_attempt_on", DateTime, nullable=False),
        Column("error_message", Text, nullable=True),
        Column("created_on", DateTime, nullable=False),
        Column("sent_on", DateTime, nullable=True),
    )
    create_index(TABLE, DUE_INDEX, ["status", "next_attempt_on"])
    create_index(TABLE, DEDUPE_INDEX, ["dedupe_key"], unique=True)
    create_fks_for_table(
        foreign_key_name=FEEDBACK_FK,
        table_name=TABLE,
        referenced_table="moh_feedback",
        local_cols=["feedback_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )
    create_fks_for_table(
        foreign_key_name=USER_FK,
        table_name=TABLE,
        referenced_table="ab_user",
        local_cols=["user_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )


def downgrade():
    drop_fks_for_table(TABLE, [FEEDBACK_FK, USER_FK])
    drop_index(TABLE, DEDUPE_INDEX)
    drop_index(TABLE, DUE_INDEX)
    drop_table(TABLE)
