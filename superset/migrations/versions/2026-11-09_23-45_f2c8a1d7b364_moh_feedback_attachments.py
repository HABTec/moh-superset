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
"""Let screenshots be attached to MoH feedback

Creates moh_feedback_attachment. The files themselves are stored on disk.

Revision ID: f2c8a1d7b364
Revises: d5b2e9c40a17
Create Date: 2026-11-09 23:45:00.000000

"""

from sqlalchemy import Column, DateTime, Integer, String
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
revision = "f2c8a1d7b364"
down_revision = "d5b2e9c40a17"

TABLE = "moh_feedback_attachment"
FEEDBACK_INDEX = "ix_moh_feedback_attachment_feedback_id"
UUID_INDEX = "uq_moh_feedback_attachment_uuid"
FEEDBACK_FK = "fk_moh_feedback_attachment_feedback_id"


def upgrade():
    create_table(
        TABLE,
        Column("id", Integer, primary_key=True),
        Column("uuid", UUIDType(binary=True), nullable=True),
        # FK → moh_feedback.id
        Column("feedback_id", Integer, nullable=False),
        Column("stored_name", String(64), nullable=False),
        Column("original_name", String(255), nullable=False),
        Column("content_type", String(20), nullable=False),
        Column("size_bytes", Integer, nullable=False),
        Column("created_on", DateTime, nullable=False),
    )
    create_index(TABLE, FEEDBACK_INDEX, ["feedback_id"])
    create_index(TABLE, UUID_INDEX, ["uuid"], unique=True)
    create_fks_for_table(
        foreign_key_name=FEEDBACK_FK,
        table_name=TABLE,
        referenced_table="moh_feedback",
        local_cols=["feedback_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )


def downgrade():
    drop_fks_for_table(TABLE, [FEEDBACK_FK])
    drop_index(TABLE, UUID_INDEX)
    drop_index(TABLE, FEEDBACK_INDEX)
    drop_table(TABLE)
