from pydantic import BaseModel


class DashboardInsights(BaseModel):
    """Generic, simplified mapping of IG Business insights. Expand as needed."""

    ig_business_id: str
    ig_username: str | None
    followers_count: int | None = None
    impressions: int | None = None
    reach: int | None = None
