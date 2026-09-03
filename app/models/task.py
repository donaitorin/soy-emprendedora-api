import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.account import Account


class TaskPriority(str, enum.Enum):
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"


class SuggestionType(str, enum.Enum):
    """Which "Atención hoy" widget a task originated from, if any.

    `None` means the user created it manually via "Agregar tarea" — the frontend uses
    this (plus `conversation_ref` for the conversation case) to decide whether a
    suggestion should still be offered today. No server-side dedup: see
    app/api/routes/tasks.py.
    """

    POSTING_REMINDER = "posting_reminder"
    UNANSWERED_CONVERSATION = "unanswered_conversation"


class Task(Base):
    """A to-do item for a business, always "for today" — no due date, no recurrence."""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority, name="task_priority", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    suggestion_type: Mapped[SuggestionType | None] = mapped_column(
        Enum(SuggestionType, name="suggestion_type", values_callable=lambda obj: [e.value for e in obj]),
        nullable=True,
    )
    # Only set when suggestion_type == unanswered_conversation: the Graph API
    # conversation id (see meta_client.get_ig_unanswered_conversations), so two
    # contacts sharing a display name aren't confused with each other. Opaque to the
    # backend — never validated against Graph API here.
    conversation_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    account: Mapped["Account"] = relationship(back_populates="tasks")
