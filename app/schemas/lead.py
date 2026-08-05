import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.lead import ArchiveReason, LeadChannel, LeadStage


class LeadCreate(BaseModel):
    name: str
    channel: LeadChannel


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    name: str
    channel: LeadChannel
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
