from datetime import datetime

from pydantic import BaseModel


class DashboardInsights(BaseModel):
    """Generic, simplified mapping of IG Business insights. Expand as needed.

    No `reach` field for the current day on purpose — see
    app/services/meta_client.py::get_ig_insights for why. `reach_yesterday` and
    `reach_two_days_ago` are always closed, already-settled days.
    """

    ig_business_id: str
    ig_username: str | None
    followers_count: int | None = None
    impressions: int | None = None
    reach_yesterday: int | None = None
    reach_two_days_ago: int | None = None


class PostingStatus(BaseModel):
    """Both fields null means the account has never posted — a valid state, not
    an error (see app/services/meta_client.py::get_ig_posting_status)."""

    last_post_at: datetime | None
    days_since_last_post: int | None


class UnansweredConversation(BaseModel):
    conversation_id: str
    contact_name: str
    hours_since_last_message: int
