import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.lead import ArchiveReason, LeadChannel, LeadStage

DESCRIPTION_MAX_LENGTH = 5000


def _normalize_markdown(v: str | None, field: str) -> str | None:
    """Trim; empty/whitespace -> None; enforce the max length after trimming."""
    if v is None:
        return None
    v = v.strip()
    if not v:
        return None
    if len(v) > DESCRIPTION_MAX_LENGTH:
        raise ValueError(f"{field} must be at most {DESCRIPTION_MAX_LENGTH} characters")
    return v


class LeadCreate(BaseModel):
    name: str
    channel: LeadChannel
    # Raw markdown, stored as-is (the frontend renders it safely). Trimmed; "" -> None.
    description: str | None = None

    @field_validator("description")
    @classmethod
    def _normalize_description(cls, v: str | None) -> str | None:
        return _normalize_markdown(v, "description")


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
    archive_note: str | None
    archived_at: datetime | None
    created_at: datetime


class LeadStageUpdate(BaseModel):
    stage: LeadStage


class LeadArchiveRequest(BaseModel):
    reason: ArchiveReason
    # Raw markdown; only kept when reason == "not_converted" (see archive_lead).
    note: str | None = None

    @field_validator("note")
    @classmethod
    def _normalize_note(cls, v: str | None) -> str | None:
        return _normalize_markdown(v, "note")


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
