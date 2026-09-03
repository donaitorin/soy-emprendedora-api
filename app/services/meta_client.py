"""Async client for Meta's OAuth code exchange and Graph API calls.

All calls that require the app secret happen server-side only — the `code` obtained
by the frontend redirect is exchanged for an access token here, never in the browser.
"""

from datetime import datetime
from typing import Any

import httpx

from app.core.config import get_settings

DEFAULT_UNANSWERED_CONVERSATIONS_LIMIT = 2

# Default for every Graph API call in this module. httpx's own default (5s) is tight
# for endpoints with nested field expansions — a slow response shouldn't take down
# the request; see MetaAPIError handling below.
_HTTP_TIMEOUT = httpx.Timeout(10.0)

# The IG conversations edge (`/{page-id}/conversations`) is known to be much slower
# than the rest of the Graph API while a Meta app is in Development Mode — observed
# taking well over the default above. Give it a lot more room before giving up.
_CONVERSATIONS_HTTP_TIMEOUT = httpx.Timeout(60.0)


class MetaAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _graph_base_url() -> str:
    settings = get_settings()
    return f"https://graph.facebook.com/{settings.meta_graph_api_version}"


def _client(timeout: httpx.Timeout = _HTTP_TIMEOUT) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout)


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
    try:
        async with _client() as client:
            response = await client.get(
                f"{_graph_base_url()}/oauth/access_token",
                params={
                    "client_id": settings.meta_app_id,
                    "client_secret": settings.meta_app_secret,
                    "redirect_uri": settings.meta_redirect_uri,
                    "code": code,
                },
            )
    except httpx.HTTPError as exc:
        raise MetaAPIError(f"Failed to reach Meta while exchanging code: {exc}") from exc
    if response.status_code != 200:
        raise MetaAPIError(f"Failed to exchange code: {response.text}", response.status_code)
    return response.json()["access_token"]


async def get_user_pages(user_access_token: str) -> list[dict[str, Any]]:
    """List Facebook Pages the user manages, including linked IG Business account if any."""
    try:
        async with _client() as client:
            response = await client.get(
                f"{_graph_base_url()}/me/accounts",
                params={
                    "access_token": user_access_token,
                    "fields": "id,name,access_token,instagram_business_account{id,username}",
                },
            )
    except httpx.HTTPError as exc:
        raise MetaAPIError(f"Failed to reach Meta while fetching pages: {exc}") from exc
    if response.status_code != 200:
        raise MetaAPIError(f"Failed to fetch pages: {response.text}", response.status_code)
    return response.json().get("data", [])


async def get_ig_insights(ig_business_id: str, page_access_token: str) -> dict[str, Any]:
    """Fetch basic IG Business insights: followers, impressions, reach.

    Metric set kept simple/generic for now — expand as the dashboard grows.
    """
    try:
        async with _client() as client:
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
    except httpx.HTTPError as exc:
        raise MetaAPIError(f"Failed to reach Meta while fetching insights: {exc}") from exc

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


async def get_ig_posting_status(ig_business_id: str, access_token: str) -> dict[str, Any]:
    """Fetch the last 10 posts and derive days elapsed since the most recent one.

    An account that never posted is a valid state (not an error) — returns None for
    both fields rather than raising.
    """
    try:
        async with _client() as client:
            response = await client.get(
                f"{_graph_base_url()}/{ig_business_id}/media",
                params={"access_token": access_token, "fields": "timestamp", "limit": 10},
            )
    except httpx.HTTPError as exc:
        raise MetaAPIError(f"Failed to reach Meta while fetching media: {exc}") from exc
    if response.status_code != 200:
        raise MetaAPIError(f"Failed to fetch media: {response.text}", response.status_code)

    timestamps = [
        datetime.fromisoformat(post["timestamp"])
        for post in response.json().get("data", [])
        if post.get("timestamp")
    ]
    if not timestamps:
        return {"last_post_at": None, "days_since_last_post": None}

    last_post_at = max(timestamps)
    return {
        "last_post_at": last_post_at,
        "days_since_last_post": (datetime.now(last_post_at.tzinfo) - last_post_at).days,
    }


async def get_ig_unanswered_conversations(
    fb_page_id: str,
    ig_business_id: str | None,
    access_token: str,
    limit: int = DEFAULT_UNANSWERED_CONVERSATIONS_LIMIT,
) -> list[dict[str, Any]]:
    """Best-effort scan of the last `limit` Instagram conversations for this Page,
    returning the ones still waiting on us (the contact's message is the most recent
    one in the thread, not ours).

    `limit` caps how many conversations are scanned *and* returned in one call — kept
    low (default 2) intentionally while this is validated against a real account; see
    docs/frontend-integration.md for the current status of that validation.
    """
    try:
        async with _client(_CONVERSATIONS_HTTP_TIMEOUT) as client:
            response = await client.get(
                f"{_graph_base_url()}/{fb_page_id}/conversations",
                params={
                    "access_token": access_token,
                    "platform": "instagram",
                    "fields": "participants,messages.limit(1){from,created_time}",
                    "limit": limit,
                },
            )
    except httpx.HTTPError as exc:
        raise MetaAPIError(f"Failed to reach Meta while fetching conversations: {exc}") from exc
    if response.status_code != 200:
        raise MetaAPIError(f"Failed to fetch conversations: {response.text}", response.status_code)

    our_ids = {fb_page_id, ig_business_id} - {None}
    results = []

    for conversation in response.json().get("data", []):
        conversation_id = conversation.get("id")
        if not conversation_id:
            continue  # can't build a stable ref for it — skip rather than guess

        messages = conversation.get("messages", {}).get("data", [])
        if not messages:
            continue

        last_message = messages[0]
        sender_id = last_message.get("from", {}).get("id")
        if sender_id in our_ids:
            continue  # we answered last — not waiting on us

        created_time_raw = last_message.get("created_time")
        if not created_time_raw:
            continue
        created_time = datetime.fromisoformat(created_time_raw)

        participants = conversation.get("participants", {}).get("data", [])
        contact = next((p for p in participants if p.get("id") not in our_ids), None)
        contact_name = (contact and (contact.get("username") or contact.get("name") or contact.get("id"))) or (
            "Desconocido"
        )

        results.append(
            {
                "conversation_id": conversation_id,
                "contact_name": contact_name,
                "hours_since_last_message": int(
                    (datetime.now(created_time.tzinfo) - created_time).total_seconds() // 3600
                ),
            }
        )

    results.sort(key=lambda r: r["hours_since_last_message"], reverse=True)
    return results


async def get_profile_picture_url(
    ig_business_id: str | None, fb_page_id: str | None, access_token: str
) -> str | None:
    """Best-effort profile picture lookup — decorative data, never raises.

    Prefers the IG Business account's picture; falls back to the Facebook Page's
    picture if there's no linked IG account. Returns None on any failure (expired
    token, rate limit, missing field, etc.) instead of propagating an error.
    """
    try:
        async with _client() as client:
            if ig_business_id:
                response = await client.get(
                    f"{_graph_base_url()}/{ig_business_id}",
                    params={"access_token": access_token, "fields": "profile_picture_url"},
                )
                if response.status_code == 200:
                    return response.json().get("profile_picture_url")
                return None

            if fb_page_id:
                response = await client.get(
                    f"{_graph_base_url()}/{fb_page_id}/picture",
                    params={"access_token": access_token, "redirect": "false"},
                )
                if response.status_code == 200:
                    return response.json().get("data", {}).get("url")
                return None
    except httpx.HTTPError:
        return None

    return None
