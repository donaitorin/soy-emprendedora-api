import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

MESSAGE_MAX_LENGTH = 5000


class SuggestionCreate(BaseModel):
    # Raw markdown, stored as-is (the frontend renders it safely). Trimmed; required.
    message: str

    @field_validator("message")
    @classmethod
    def _normalize_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message must not be empty")
        if len(v) > MESSAGE_MAX_LENGTH:
            raise ValueError(f"message must be at most {MESSAGE_MAX_LENGTH} characters")
        return v


class SuggestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    user_id: uuid.UUID
    message: str
    created_at: datetime


class SuggestionAdminRead(SuggestionRead):
    account_name: str
    user_email: str
    user_first_name: str
    user_last_name: str


class SuggestionPage(BaseModel):
    items: list[SuggestionAdminRead]
    page: int
    page_size: int
    total: int
    total_pages: int
