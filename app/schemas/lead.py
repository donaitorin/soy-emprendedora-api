import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.lead import ArchiveReason, LeadChannel, LeadStage

DESCRIPTION_MAX_LENGTH = 5000


class LeadCreate(BaseModel):
    name: str
    channel: LeadChannel
    # Raw markdown, stored as-is (the frontend renders it safely). Trimmed; "" -> None.
    description: str | None = None

    @field_validator("description")
    @classmethod
    def _normalize_description(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if len(v) > DESCRIPTION_MAX_LENGTH:
            raise ValueError(f"description must be at most {DESCRIPTION_MAX_LENGTH} characters")
        return v


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    name: str
    channel: LeadChannel
    description: str | None
    stage: LeadStage
    stage_changed_at: datetime
    converted_at: datetime | None
    archived: bool
    archive_reason: ArchiveReason | None
    archived_at: datetime | None
    created_at: datetime


class LeadStageUpdate(BaseModel):
    stage: LeadStage


class LeadArchiveRequest(BaseModel):
    reason: ArchiveReason


class LeadPage(BaseModel):
    items: list[LeadRead]
    page: int
    page_size: int
    total: int
    total_pages: int


class LeadStats(BaseModel):
    active_count: int
    conversion_rate: float | None
    avg_conversion_days: float | None
