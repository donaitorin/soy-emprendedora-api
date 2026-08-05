import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.account import Account


class LeadChannel(str, enum.Enum):
    INSTAGRAM = "instagram"
    WHATSAPP = "whatsapp"
    REFERIDO = "referido"
    WEB = "web"
    OTRO = "otro"


class LeadStage(str, enum.Enum):
    NUEVO = "nuevo"
    CONVERSACION = "conversacion"
    PROPUESTA = "propuesta"
    AGENDADA = "agendada"
    CONVERTIDA = "convertida"


class ArchiveReason(str, enum.Enum):
    CONVERTED = "converted"
    NOT_CONVERTED = "not_converted"


class Lead(Base):
    """A lead in the kanban board, scoped to a business (`account_id`).

    `archived` is separate from soft delete (`deleted_at`): an archived lead still
    counts for stats and still exists in the paginated table, it's just off the
    board. A soft-deleted lead is excluded from everything (board, table, stats) —
    see app/api/routes/leads.py for where each state is filtered out.
    """

    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    channel: Mapped[LeadChannel] = mapped_column(
        Enum(LeadChannel, name="lead_channel", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    stage: Mapped[LeadStage] = mapped_column(
        Enum(LeadStage, name="lead_stage", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=LeadStage.NUEVO,
    )
    stage_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archive_reason: Mapped[ArchiveReason | None] = mapped_column(
        Enum(ArchiveReason, name="archive_reason", values_callable=lambda obj: [e.value for e in obj]),
        nullable=True,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Soft delete: a non-null deleted_at excludes this row from the board, the
    # paginated table, and every stat — same pattern as MoneyMovement.deleted_at.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped["Account"] = relationship(back_populates="leads")
