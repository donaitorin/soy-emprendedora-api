import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.user import PlatformRole


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    first_name: str
    last_name: str
    role: PlatformRole
    is_active: bool
    created_at: datetime


class UserUpdateAdmin(BaseModel):
    """Fields a platform admin may edit on any user."""

    first_name: str | None = None
    last_name: str | None = None
    role: PlatformRole | None = None
    is_active: bool | None = None
