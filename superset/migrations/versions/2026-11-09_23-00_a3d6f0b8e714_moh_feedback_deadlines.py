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
"""Add a priority and deadlines to MoH feedback

Existing items become normal priority, with deadlines counted from when they
were sent.

Revision ID: a3d6f0b8e714
Revises: c7f4a8e2d915
Create Date: 2026-11-09 23:00:00.000000

"""

from datetime import datetime, time, timedelta

from alembic import op
from sqlalchemy import (
    Column,
    column,
    DateTime,
    Integer,
    select,
    String,
    table,
)

from superset.migrations.shared.utils import (
    add_columns,
    create_index,
    drop_columns,
    drop_index,
)

# revision identifiers, used by Alembic.
revision = "a3d6f0b8e714"
down_revision = "c7f4a8e2d915"

FEEDBACK_TABLE = "moh_feedback"
DUE_INDEX = "ix_moh_feedback_status_due_on"
ADDIS_ABABA_OFFSET = timedelta(hours=3)
NORMAL_FIRST_RESPONSE_DAYS = 5
NORMAL_DUE_DAYS = 14

feedback = table(
    FEEDBACK_TABLE,
    column("id", Integer),
    column("created_on", DateTime),
    column("clock_started_on", DateTime),
    column("first_response_due_on", DateTime),
    column("due_on", DateTime),
)


def _deadline(sent_on, working_days):
    """Return the end of the local day that many Monday-to-Friday days later."""
    day = (sent_on + ADDIS_ABABA_OFFSET).date()
    remaining = working_days
    while remaining > 0:
        day += timedelta(days=1)
        if day.weekday() < 5:
            remaining -= 1
    return datetime.combine(day, time(23, 59, 59)) - ADDIS_ABABA_OFFSET


def upgrade():
    add_columns(
        FEEDBACK_TABLE,
        Column("priority", String(10), nullable=False, server_default="normal"),
        Column("clock_started_on", DateTime, nullable=True),
        Column("paused_on", DateTime, nullable=True),
        Column("paused_days", Integer, nullable=False, server_default="0"),
        Column("first_response_due_on", DateTime, nullable=True),
        Column("due_on", DateTime, nullable=True),
    )
    create_index(FEEDBACK_TABLE, DUE_INDEX, ["status", "due_on"])

    bind = op.get_bind()
    rows = bind.execute(select(feedback.c.id, feedback.c.created_on)).fetchall()
    for feedback_id, sent_on in rows:
        bind.execute(
            feedback.update()
            .where(feedback.c.id == feedback_id)
            .values(
                clock_started_on=sent_on,
                first_response_due_on=_deadline(sent_on, NORMAL_FIRST_RESPONSE_DAYS),
                due_on=_deadline(sent_on, NORMAL_DUE_DAYS),
            )
        )


def downgrade():
    drop_index(FEEDBACK_TABLE, DUE_INDEX)
    drop_columns(
        FEEDBACK_TABLE,
        "priority",
        "clock_started_on",
        "paused_on",
        "paused_days",
        "first_response_due_on",
        "due_on",
    )
