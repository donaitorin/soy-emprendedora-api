"""Async client for Meta's OAuth code exchange and Graph API calls.

All calls that require the app secret happen server-side only — the `code` obtained
by the frontend redirect is exchanged for an access token here, never in the browser.
"""

from typing import Any

import httpx

from app.core.config import get_settings


class MetaAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _graph_base_url() -> str:
    settings = get_settings()
    return f"https://graph.facebook.com/{settings.meta_graph_api_version}"


def build_oauth_url(state: str) -> str:
    settings = get_settings()
    params = httpx.QueryParams(
        {
            "client_id": settings.meta_app_id,
            "redirect_uri": settings.meta_redirect_uri,
            "state": state,
            "scope": settings.meta_oauth_scopes,
            "response_type": "code",
        }
    )
    return f"https://www.facebook.com/{settings.meta_graph_api_version}/dialog/oauth?{params}"


async def exchange_code_for_token(code: str) -> str:
    """Exchange an OAuth `code` for a user access token."""
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{_graph_base_url()}/oauth/access_token",
            params={
                "client_id": settings.meta_app_id,
                "client_secret": settings.meta_app_secret,
                "redirect_uri": settings.meta_redirect_uri,
                "code": code,
            },
        )
    if response.status_code != 200:
        raise MetaAPIError(f"Failed to exchange code: {response.text}", response.status_code)
    return response.json()["access_token"]


async def get_user_pages(user_access_token: str) -> list[dict[str, Any]]:
    """List Facebook Pages the user manages, including linked IG Business account if any."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{_graph_base_url()}/me/accounts",
            params={
                "access_token": user_access_token,
                "fields": "id,name,access_token,instagram_business_account{id,username}",
            },
        )
    if response.status_code != 200:
        raise MetaAPIError(f"Failed to fetch pages: {response.text}", response.status_code)
    return response.json().get("data", [])


async def get_ig_insights(ig_business_id: str, page_access_token: str) -> dict[str, Any]:
    """Fetch basic IG Business insights: followers, impressions, reach.

    Metric set kept simple/generic for now — expand as the dashboard grows.
    """
    async with httpx.AsyncClient() as client:
        profile_response = await client.get(
            f"{_graph_base_url()}/{ig_business_id}",
            params={"access_token": page_access_token, "fields": "username,followers_count"},
        )
        insights_response = await client.get(
            f"{_graph_base_url()}/{ig_business_id}/insights",
            params={
                "access_token": page_access_token,
                "metric": "impressions,reach",
                "period": "day",
            },
        )

    if profile_response.status_code != 200:
        raise MetaAPIError(f"Failed to fetch IG profile: {profile_response.text}", profile_response.status_code)

    profile = profile_response.json()
    metrics: dict[str, int] = {}
    if insights_response.status_code == 200:
        for entry in insights_response.json().get("data", []):
            values = entry.get("values", [])
            if values:
                metrics[entry["name"]] = values[-1].get("value")

    return {
        "ig_username": profile.get("username"),
        "followers_count": profile.get("followers_count"),
        "impressions": metrics.get("impressions"),
        "reach": metrics.get("reach"),
    }
