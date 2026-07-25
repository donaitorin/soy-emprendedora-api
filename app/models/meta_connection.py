import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.account import Account


class MetaConnection(Base):
    """A business's connection to a Meta/Facebook Page + Instagram Business account.

    Modeled as one account -> many meta_connections (historical / multi-page ready),
    even though today each business only has a single active row (is_primary=True).
    The "active" connection is resolved via query, not via a unique required FK.
    """

    __tablename__ = "meta_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    fb_page_id: Mapped[str] = mapped_column(String, nullable=False)
    ig_business_id: Mapped[str | None] = mapped_column(String, nullable=True)
    page_name: Mapped[str | None] = mapped_column(String, nullable=True)
    ig_username: Mapped[str | None] = mapped_column(String, nullable=True)
    # Meta's access_token, Fernet-encrypted. Never serialized in any API response.
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    account: Mapped["Account"] = relationship(back_populates="meta_connections")
