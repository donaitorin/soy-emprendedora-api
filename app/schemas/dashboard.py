from datetime import datetime

from pydantic import BaseModel


class DashboardInsights(BaseModel):
    """Generic, simplified mapping of IG Business insights. Expand as needed."""

    ig_business_id: str
    ig_username: str | None
    followers_count: int | None = None
    impressions: int | None = None
    reach: int | None = None


class PostingStatus(BaseModel):
    """Both fields null means the account has never posted — a valid state, not
    an error (see app/services/meta_client.py::get_ig_posting_status)."""

    last_post_at: datetime | None
    days_since_last_post: int | None


class UnansweredConversation(BaseModel):
    conversation_id: str
    contact_name: str
    hours_since_last_message: int
