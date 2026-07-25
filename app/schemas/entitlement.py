import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.entitlement import EntitlementStatus


class EntitlementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    plan: str
    status: EntitlementStatus
    source: str
    external_ref: str | None
    current_period_end: datetime | None
    created_at: datetime
    updated_at: datetime


class EntitlementCreate(BaseModel):
    plan: str
    status: EntitlementStatus = EntitlementStatus.ACTIVE
    source: str = "manual"
    external_ref: str | None = None
    current_period_end: datetime | None = None


class EntitlementUpdate(BaseModel):
    status: EntitlementStatus | None = None
    plan: str | None = None
    current_period_end: datetime | None = None
