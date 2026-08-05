import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.entitlement import Entitlement
    from app.models.lead import Lead
    from app.models.meta_connection import MetaConnection
    from app.models.money_movement import MoneyMovement
    from app.models.user_account import UserAccount


class Account(Base):
    """Represents a business (not a person)."""

    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user_accounts: Mapped[list["UserAccount"]] = relationship(back_populates="account")
    entitlements: Mapped[list["Entitlement"]] = relationship(back_populates="account")
    meta_connections: Mapped[list["MetaConnection"]] = relationship(back_populates="account")
    money_movements: Mapped[list["MoneyMovement"]] = relationship(back_populates="account")
    leads: Mapped[list["Lead"]] = relationship(back_populates="account")
