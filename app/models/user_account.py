import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.user import User


class BusinessRole(str, enum.Enum):
    """Role of a user *within a specific business*, independent of the platform role."""

    OWNER = "owner"
    COLLABORATOR = "collaborator"


class UserAccount(Base):
    """Bridge table (many-to-many) between users and accounts (businesses).

    Today, business logic only allows a single account per user, but this is enforced
    at the service layer only (see app/api/routes/auth.py and accounts.py) — NOT at the
    database or model level — so that constraint can be relaxed later (multiple
    businesses per user) without a schema migration.
    """

    __tablename__ = "user_accounts"
    __table_args__ = (UniqueConstraint("user_id", "account_id", name="uq_user_account"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[BusinessRole] = mapped_column(
        Enum(BusinessRole, name="business_role", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="user_accounts")
    account: Mapped["Account"] = relationship(back_populates="user_accounts")
