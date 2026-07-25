import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.account import Account


class EntitlementStatus(str, enum.Enum):
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    REVOKED = "revoked"


class Entitlement(Base):
    """An account's plan/access grant.

    Modeled as one account -> many entitlements (historical), even though today each
    account only ever has a single *effective* one. The "current" entitlement is never
    read from a single required field — always resolved via query
    (see app/api/deps.py::check_entitlement), so status changes just add new rows.
    """

    __tablename__ = "entitlements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    plan: Mapped[str] = mapped_column(String, nullable=False, default="free")
    status: Mapped[EntitlementStatus] = mapped_column(
        Enum(EntitlementStatus, name="entitlement_status"), nullable=False, default=EntitlementStatus.ACTIVE
    )
    source: Mapped[str] = mapped_column(String, nullable=False, default="manual")
    external_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    account: Mapped["Account"] = relationship(back_populates="entitlements")
