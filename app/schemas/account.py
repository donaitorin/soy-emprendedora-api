import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.user_account import BusinessRole


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_at: datetime


class AccountWithRole(AccountRead):
    """An account together with the requesting user's role within it."""

    my_role: BusinessRole


class AccountUpdate(BaseModel):
    name: str | None = None
