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
"""Let a named person be added to MoH feedback

Creates moh_feedback_participant, for the people added to an item, and
moh_feedback_person_search, which limits how often a user can search for people.

Revision ID: c7f4a8e2d915
Revises: e1a9d3c75b02
Create Date: 2026-11-09 22:00:00.000000

"""

from alembic import op
from sqlalchemy import Column, DateTime, Integer, String, Text, text

from superset.migrations.shared.utils import (
    create_fks_for_table,
    create_index,
    create_table,
    drop_fks_for_table,
    drop_index,
    drop_table,
)

# revision identifiers, used by Alembic.
revision = "c7f4a8e2d915"
down_revision = "e1a9d3c75b02"

PARTICIPANT_TABLE = "moh_feedback_participant"
SEARCH_TABLE = "moh_feedback_person_search"
ACTIVE_INDEX = "uq_moh_feedback_participant_active"
USER_INDEX = "ix_moh_feedback_participant_user_id"
ADDED_BY_INDEX = "ix_moh_feedback_participant_added_by_added_on"
SEARCH_INDEX = "ix_moh_feedback_person_search_user_searched"
PARTICIPANT_FKS = (
    (
        "fk_moh_feedback_participant_feedback_id",
        "feedback_id",
        "moh_feedback",
        "CASCADE",
    ),
    ("fk_moh_feedback_participant_user_id", "user_id", "ab_user", "CASCADE"),
    ("fk_moh_feedback_participant_added_by_fk", "added_by_fk", "ab_user", "SET NULL"),
    (
        "fk_moh_feedback_participant_removed_by_fk",
        "removed_by_fk",
        "ab_user",
        "SET NULL",
    ),
)
SEARCH_FK = "fk_moh_feedback_person_search_user_id"


def upgrade():
    create_table(
        PARTICIPANT_TABLE,
        Column("id", Integer, primary_key=True),
        # FK → moh_feedback.id
        Column("feedback_id", Integer, nullable=False),
        # FK → ab_user.id
        Column("user_id", Integer, nullable=False),
        # FK → ab_user.id
        Column("added_by_fk", Integer, nullable=True),
        Column("display_name", String(255), nullable=False),
        Column("unit_path", Text, nullable=True),
        Column("added_on", DateTime, nullable=False),
        Column("removed_on", DateTime, nullable=True),
        # FK → ab_user.id
        Column("removed_by_fk", Integer, nullable=True),
    )
    create_index(PARTICIPANT_TABLE, USER_INDEX, ["user_id"])
    create_index(PARTICIPANT_TABLE, ADDED_BY_INDEX, ["added_by_fk", "added_on"])
    # A person is on an item once; the shared helper has no partial-index option
    op.create_index(
        ACTIVE_INDEX,
        PARTICIPANT_TABLE,
        ["feedback_id", "user_id"],
        unique=True,
        postgresql_where=text("removed_on IS NULL"),
        sqlite_where=text("removed_on IS NULL"),
    )
    for name, column, referenced_table, ondelete in PARTICIPANT_FKS:
        create_fks_for_table(
            foreign_key_name=name,
            table_name=PARTICIPANT_TABLE,
            referenced_table=referenced_table,
            local_cols=[column],
            remote_cols=["id"],
            ondelete=ondelete,
        )

    create_table(
        SEARCH_TABLE,
        Column("id", Integer, primary_key=True),
        # FK → ab_user.id
        Column("user_id", Integer, nullable=False),
        Column("searched_on", DateTime, nullable=False),
    )
    create_index(SEARCH_TABLE, SEARCH_INDEX, ["user_id", "searched_on"])
    create_fks_for_table(
        foreign_key_name=SEARCH_FK,
        table_name=SEARCH_TABLE,
        referenced_table="ab_user",
        local_cols=["user_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )


def downgrade():
    drop_fks_for_table(SEARCH_TABLE, [SEARCH_FK])
    drop_index(SEARCH_TABLE, SEARCH_INDEX)
    drop_table(SEARCH_TABLE)

    drop_fks_for_table(PARTICIPANT_TABLE, [fk[0] for fk in PARTICIPANT_FKS])
    drop_index(PARTICIPANT_TABLE, ACTIVE_INDEX)
    drop_index(PARTICIPANT_TABLE, ADDED_BY_INDEX)
    drop_index(PARTICIPANT_TABLE, USER_INDEX)
    drop_table(PARTICIPANT_TABLE)
