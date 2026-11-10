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
"""MoH feedback loop — SQLAlchemy models.

- moh_feedback        — one row per item of feedback
- moh_feedback_event  — append-only history of each item
- moh_feedback_unit_access — the units that can read an item, and which one acts
- moh_feedback_participant — the people added to an item by name
- moh_feedback_person_search — when each user searched for a person
- moh_feedback_notification — the emails waiting to be sent, and what happened
- moh_feedback_attachment — the screenshots sent with an item
"""

from datetime import datetime, timezone

from flask_appbuilder import Model
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    false,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import relationship

from superset.models.helpers import UUIDMixin


def _utc_now() -> datetime:
    """Current UTC time as the naive datetime stored in these tables."""
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


class MohFeedback(UUIDMixin, Model):
    """One item of feedback.

    The sender's details are copied at send time, so the record stays readable
    if the account or its org unit later changes.
    """

    __tablename__ = "moh_feedback"

    id = Column(Integer, primary_key=True)
    # Generated when the form is displayed, so a repeated submit saves one item
    submission_id = Column(String(64), nullable=False, unique=True)

    created_by_fk = Column(
        Integer, ForeignKey("ab_user.id", ondelete="SET NULL"), nullable=True
    )
    sender_name = Column(String(255), nullable=False)
    sender_email = Column(String(320), nullable=True)
    sender_role = Column(String(255), nullable=True)

    # None when the sender has no org unit or the lookup was unavailable
    origin_unit_id = Column(String(32), nullable=True)
    origin_path = Column(Text, nullable=True)
    origin_level1id = Column(String(32), nullable=True)
    origin_level2id = Column(String(32), nullable=True)
    origin_level3id = Column(String(32), nullable=True)
    origin_level4id = Column(String(32), nullable=True)
    origin_level5id = Column(String(32), nullable=True)
    origin_level6id = Column(String(32), nullable=True)
    origin_level7id = Column(String(32), nullable=True)

    # "up" to the level above the sender, or "down" to a unit in their area
    direction = Column(String(10), nullable=False, default="up", server_default="up")
    # None while the item is waiting to be routed
    target_unit_id = Column(String(32), nullable=True)
    target_unit_name = Column(String(255), nullable=True)
    target_path = Column(Text, nullable=True)

    type = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    # Set when a handler hides content that holds patient details
    hidden_on = Column(DateTime, nullable=True)
    page_url = Column(String(2048), nullable=True)

    status = Column(String(20), nullable=False, default="new", server_default="new")
    closure_reason = Column(String(20), nullable=True)
    priority = Column(
        String(10), nullable=False, default="normal", server_default="normal"
    )
    # Deadlines count from here; it restarts when the item moves to another unit
    clock_started_on = Column(DateTime, nullable=True)
    # Set while the item is waiting on the sender
    paused_on = Column(DateTime, nullable=True)
    paused_days = Column(Integer, nullable=False, default=0, server_default="0")
    first_response_due_on = Column(DateTime, nullable=True)
    due_on = Column(DateTime, nullable=True)
    assigned_to_fk = Column(
        Integer, ForeignKey("ab_user.id", ondelete="SET NULL"), nullable=True
    )
    assignee_name = Column(String(255), nullable=True)
    first_response_on = Column(DateTime, nullable=True)
    answered_on = Column(DateTime, nullable=True)
    closed_on = Column(DateTime, nullable=True)
    created_on = Column(DateTime, nullable=False, default=_utc_now)
    changed_on = Column(DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)

    events = relationship(
        "MohFeedbackEvent",
        back_populates="feedback",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    unit_access = relationship(
        "MohFeedbackUnitAccess",
        back_populates="feedback",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    participants = relationship(
        "MohFeedbackParticipant",
        back_populates="feedback",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="MohFeedbackParticipant.id",
    )
    attachments = relationship(
        "MohFeedbackAttachment",
        back_populates="feedback",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="MohFeedbackAttachment.id",
    )
    notifications = relationship(
        "MohFeedbackNotification",
        back_populates="feedback",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_moh_feedback_created_by_created_on", "created_by_fk", "created_on"),
        Index("ix_moh_feedback_status_due_on", "status", "due_on"),
    )

    @property
    def active_participants(self) -> list["MohFeedbackParticipant"]:
        """The people who are added to this item and have not been removed."""
        return [row for row in self.participants if row.removed_on is None]

    @property
    def display_status(self) -> str:
        """The status shown to users; a declined item is shown as declined."""
        return self.closure_reason or self.status

    @property
    def reference(self) -> str:
        """The number shown to users, such as ``FB-1042``."""
        return f"FB-{self.id}"

    def __repr__(self) -> str:
        return f"<MohFeedback {self.id} status={self.status!r}>"


class MohFeedbackEvent(Model):
    """One entry in an item's history. Rows are added and never changed."""

    __tablename__ = "moh_feedback_event"

    id = Column(Integer, primary_key=True)
    feedback_id = Column(
        Integer, ForeignKey("moh_feedback.id", ondelete="CASCADE"), nullable=False
    )
    event_type = Column(String(30), nullable=False)
    from_status = Column(String(20), nullable=True)
    to_status = Column(String(20), nullable=True)
    # None means the system recorded the event
    user_id = Column(
        Integer, ForeignKey("ab_user.id", ondelete="SET NULL"), nullable=True
    )
    actor_name = Column(String(255), nullable=True)
    from_unit_id = Column(String(32), nullable=True)
    to_unit_id = Column(String(32), nullable=True)
    message = Column(Text, nullable=True)
    hidden_on = Column(DateTime, nullable=True)
    # Internal entries are never shown to the sender
    is_internal = Column(Boolean, nullable=False, default=False, server_default=false())
    created_on = Column(DateTime, nullable=False, default=_utc_now)

    feedback = relationship("MohFeedback", back_populates="events")

    __table_args__ = (Index("ix_moh_feedback_event_feedback_id", "feedback_id"),)

    def __repr__(self) -> str:
        return f"<MohFeedbackEvent {self.id} type={self.event_type!r}>"


class MohFeedbackUnitAccess(Model):
    """A unit that can read an item. The current row is the unit responsible."""

    __tablename__ = "moh_feedback_unit_access"

    id = Column(Integer, primary_key=True)
    feedback_id = Column(
        Integer, ForeignKey("moh_feedback.id", ondelete="CASCADE"), nullable=False
    )
    unit_id = Column(String(32), nullable=False)
    unit_name = Column(String(255), nullable=True)
    reason = Column(String(20), nullable=False)
    is_current = Column(Boolean, nullable=False, default=True)
    granted_on = Column(DateTime, nullable=False, default=_utc_now)

    feedback = relationship("MohFeedback", back_populates="unit_access")

    __table_args__ = (
        Index("ix_moh_feedback_unit_access_unit_id", "unit_id"),
        Index(
            "uq_moh_feedback_unit_access_current",
            "feedback_id",
            unique=True,
            postgresql_where=text("is_current"),
            sqlite_where=text("is_current = 1"),
        ),
    )

    def __repr__(self) -> str:
        return f"<MohFeedbackUnitAccess {self.feedback_id} unit={self.unit_id!r}>"


class MohFeedbackParticipant(Model):
    """A person added to an item by name. They never become responsible for it.

    The name and path are as shown to whoever added the person. Removing someone
    keeps the row, so the record of who could read the item is preserved.
    """

    __tablename__ = "moh_feedback_participant"

    id = Column(Integer, primary_key=True)
    feedback_id = Column(
        Integer, ForeignKey("moh_feedback.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(
        Integer, ForeignKey("ab_user.id", ondelete="CASCADE"), nullable=False
    )
    added_by_fk = Column(
        Integer, ForeignKey("ab_user.id", ondelete="SET NULL"), nullable=True
    )
    display_name = Column(String(255), nullable=False)
    # One path per line; None when the person has no org unit
    unit_path = Column(Text, nullable=True)
    added_on = Column(DateTime, nullable=False, default=_utc_now)
    removed_on = Column(DateTime, nullable=True)
    removed_by_fk = Column(
        Integer, ForeignKey("ab_user.id", ondelete="SET NULL"), nullable=True
    )

    feedback = relationship("MohFeedback", back_populates="participants")

    __table_args__ = (
        Index("ix_moh_feedback_participant_user_id", "user_id"),
        Index(
            "ix_moh_feedback_participant_added_by_added_on", "added_by_fk", "added_on"
        ),
        Index(
            "uq_moh_feedback_participant_active",
            "feedback_id",
            "user_id",
            unique=True,
            postgresql_where=text("removed_on IS NULL"),
            sqlite_where=text("removed_on IS NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<MohFeedbackParticipant {self.feedback_id} user={self.user_id}>"


class MohFeedbackAttachment(UUIDMixin, Model):
    """A screenshot sent with an item. The file itself is stored on disk."""

    __tablename__ = "moh_feedback_attachment"

    id = Column(Integer, primary_key=True)
    feedback_id = Column(
        Integer, ForeignKey("moh_feedback.id", ondelete="CASCADE"), nullable=False
    )
    # A random name, so a file cannot be found from what the sender called it
    stored_name = Column(String(64), nullable=False)
    original_name = Column(String(255), nullable=False)
    content_type = Column(String(20), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    hidden_on = Column(DateTime, nullable=True)
    created_on = Column(DateTime, nullable=False, default=_utc_now)

    feedback = relationship("MohFeedback", back_populates="attachments")

    __table_args__ = (Index("ix_moh_feedback_attachment_feedback_id", "feedback_id"),)

    def __repr__(self) -> str:
        return f"<MohFeedbackAttachment {self.id} feedback={self.feedback_id}>"


class MohFeedbackNotification(Model):
    """An email to send. A row for a unit becomes one row per handler."""

    __tablename__ = "moh_feedback_notification"

    id = Column(Integer, primary_key=True)
    # None for a daily summary, which covers many items
    feedback_id = Column(
        Integer, ForeignKey("moh_feedback.id", ondelete="CASCADE"), nullable=True
    )
    user_id = Column(
        Integer, ForeignKey("ab_user.id", ondelete="CASCADE"), nullable=True
    )
    unit_id = Column(String(32), nullable=True)
    # Whoever caused the email is not sent it
    exclude_user_id = Column(Integer, nullable=True)
    kind = Column(String(30), nullable=False)
    actor_name = Column(String(255), nullable=True)
    detail = Column(Text, nullable=True)
    # Stops a job that runs twice from queueing the same email twice
    dedupe_key = Column(String(120), nullable=True)
    status = Column(String(10), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_on = Column(DateTime, nullable=False, default=_utc_now)
    error_message = Column(Text, nullable=True)
    created_on = Column(DateTime, nullable=False, default=_utc_now)
    sent_on = Column(DateTime, nullable=True)

    feedback = relationship("MohFeedback", back_populates="notifications")

    __table_args__ = (
        Index("ix_moh_feedback_notification_status_next", "status", "next_attempt_on"),
        Index("uq_moh_feedback_notification_dedupe", "dedupe_key", unique=True),
    )

    def __repr__(self) -> str:
        return f"<MohFeedbackNotification {self.id} kind={self.kind!r}>"


class MohFeedbackPersonSearch(Model):
    """When a user searched for a person. The search text is never stored."""

    __tablename__ = "moh_feedback_person_search"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("ab_user.id", ondelete="CASCADE"), nullable=False
    )
    searched_on = Column(DateTime, nullable=False, default=_utc_now)

    __table_args__ = (
        Index("ix_moh_feedback_person_search_user_searched", "user_id", "searched_on"),
    )

    def __repr__(self) -> str:
        return f"<MohFeedbackPersonSearch {self.id} user={self.user_id}>"
