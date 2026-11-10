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
"""Let handlers hide MoH feedback content that holds patient details

Adds hidden_on to feedback, history entries and screenshots.

Revision ID: 9a1e4c7d2b50
Revises: f2c8a1d7b364
Create Date: 2026-11-10 08:00:00.000000

"""

from sqlalchemy import Column, DateTime

from superset.migrations.shared.utils import add_columns, drop_columns

# revision identifiers, used by Alembic.
revision = "9a1e4c7d2b50"
down_revision = "f2c8a1d7b364"

TABLES = ("moh_feedback", "moh_feedback_event", "moh_feedback_attachment")


def upgrade():
    for table in TABLES:
        add_columns(table, Column("hidden_on", DateTime, nullable=True))


def downgrade():
    for table in TABLES:
        drop_columns(table, "hidden_on")
