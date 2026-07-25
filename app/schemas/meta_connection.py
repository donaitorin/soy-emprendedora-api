import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MetaConnectionStatus(BaseModel):
    """Public-safe view of a connection — never includes the access token."""

    model_config = ConfigDict(from_attributes=True)

    connected: bool
    fb_page_id: str | None = None
    ig_business_id: str | None = None
    page_name: str | None = None
    ig_username: str | None = None
    token_expires_at: datetime | None = None
    is_primary: bool | None = None


class MetaPageOption(BaseModel):
    """One of the Facebook Pages available to the user during OAuth connect,
    offered for selection when more than one is available."""

    fb_page_id: str
    page_name: str
    ig_business_id: str | None = None
    ig_username: str | None = None


class MetaCallbackResult(BaseModel):
    account_id: uuid.UUID
    pages: list[MetaPageOption]
    requires_selection: bool


class MetaSelectPageRequest(BaseModel):
    account_id: uuid.UUID
    fb_page_id: str
