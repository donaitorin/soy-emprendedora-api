import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.user_account import BusinessRole


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    email: EmailStr
    first_name: str
    last_name: str
    role: BusinessRole
    created_at: datetime


class MemberCreate(BaseModel):
    email: EmailStr
