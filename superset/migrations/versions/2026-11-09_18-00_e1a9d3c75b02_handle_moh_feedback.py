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
"""Let units handle and answer MoH feedback

Adds to moh_feedback the assignee, response times and closure reason, and marks
which history entries are internal.

Revision ID: e1a9d3c75b02
Revises: b4e7c2a91f30
Create Date: 2026-11-09 18:00:00.000000

"""

from sqlalchemy import Boolean, Column, DateTime, false, Integer, String

from superset.migrations.shared.utils import (
    add_columns,
    create_fks_for_table,
    create_index,
    drop_columns,
    drop_fks_for_table,
    drop_index,
)

# revision identifiers, used by Alembic.
revision = "e1a9d3c75b02"
down_revision = "b4e7c2a91f30"

FEEDBACK_TABLE = "moh_feedback"
EVENT_TABLE = "moh_feedback_event"
ASSIGNEE_FK = "fk_moh_feedback_assigned_to_fk"
ASSIGNEE_INDEX = "ix_moh_feedback_assigned_to_status"


def upgrade():
    add_columns(
        FEEDBACK_TABLE,
        # FK → ab_user.id
        Column("assigned_to_fk", Integer, nullable=True),
        Column("assignee_name", String(255), nullable=True),
        Column("first_response_on", DateTime, nullable=True),
        Column("answered_on", DateTime, nullable=True),
        Column("closed_on", DateTime, nullable=True),
        Column("closure_reason", String(20), nullable=True),
    )
    add_columns(
        EVENT_TABLE,
        Column("is_internal", Boolean, nullable=False, server_default=false()),
    )
    create_index(FEEDBACK_TABLE, ASSIGNEE_INDEX, ["assigned_to_fk", "status"])
    create_fks_for_table(
        foreign_key_name=ASSIGNEE_FK,
        table_name=FEEDBACK_TABLE,
        referenced_table="ab_user",
        local_cols=["assigned_to_fk"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )


def downgrade():
    drop_fks_for_table(FEEDBACK_TABLE, [ASSIGNEE_FK])
    drop_index(FEEDBACK_TABLE, ASSIGNEE_INDEX)
    drop_columns(EVENT_TABLE, "is_internal")
    drop_columns(
        FEEDBACK_TABLE,
        "assigned_to_fk",
        "assignee_name",
        "first_response_on",
        "answered_on",
        "closed_on",
        "closure_reason",
    )
