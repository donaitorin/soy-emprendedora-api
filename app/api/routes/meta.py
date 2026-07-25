import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_business_access, get_current_user, require_business_access
from app.core.security import create_meta_oauth_state, decode_meta_oauth_state, encrypt_secret
from app.db.session import get_db
from app.models.meta_connection import MetaConnection
from app.models.user import User
from app.schemas.meta_connection import (
    MetaCallbackResult,
    MetaConnectionStatus,
    MetaPageOption,
    MetaSelectPageRequest,
)
from app.services import meta_client

router = APIRouter(prefix="/meta", tags=["meta"])

# In-memory cache of page options per account, keyed by account_id, populated by the
# OAuth callback and consumed by /meta/select-page. A single-process cache is fine for
# this short-lived, per-connection-attempt data; move to Redis/DB if scaled out.
_pending_page_selection: dict[uuid.UUID, list[dict]] = {}


@router.get("/connect")
async def connect(
    account_id: uuid.UUID = Query(...),
    _=Depends(require_business_access),
) -> RedirectResponse:
    state = create_meta_oauth_state(account_id)
    return RedirectResponse(meta_client.build_oauth_url(state))


@router.get("/callback", response_model=MetaCallbackResult)
async def callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> MetaCallbackResult:
    try:
        account_id = decode_meta_oauth_state(state)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired state")

    user_access_token = await meta_client.exchange_code_for_token(code)
    pages = await meta_client.get_user_pages(user_access_token)

    if not pages:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No Facebook Pages available for this account")

    _pending_page_selection[account_id] = pages

    if len(pages) == 1:
        await _persist_connection(db, account_id, pages[0])
        del _pending_page_selection[account_id]
        return MetaCallbackResult(account_id=account_id, pages=[], requires_selection=False)

    options = [
        MetaPageOption(
            fb_page_id=page["id"],
            page_name=page["name"],
            ig_business_id=(page.get("instagram_business_account") or {}).get("id"),
            ig_username=(page.get("instagram_business_account") or {}).get("username"),
        )
        for page in pages
    ]
    return MetaCallbackResult(account_id=account_id, pages=options, requires_selection=True)


@router.post("/select-page", response_model=MetaConnectionStatus)
async def select_page(
    payload: MetaSelectPageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MetaConnectionStatus:
    await ensure_business_access(user, payload.account_id, db)

    pages = _pending_page_selection.get(payload.account_id)
    if not pages:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No pending page selection for this business")

    page = next((p for p in pages if p["id"] == payload.fb_page_id), None)
    if page is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Page not found in the pending selection")

    connection = await _persist_connection(db, payload.account_id, page)
    del _pending_page_selection[payload.account_id]
    return _to_status(connection)


async def _persist_connection(db: AsyncSession, account_id: uuid.UUID, page: dict) -> MetaConnection:
    ig_account = page.get("instagram_business_account") or {}

    existing = await db.execute(
        select(MetaConnection).where(MetaConnection.account_id == account_id, MetaConnection.is_primary)
    )
    for old in existing.scalars().all():
        old.is_primary = False

    connection = MetaConnection(
        account_id=account_id,
        fb_page_id=page["id"],
        ig_business_id=ig_account.get("id"),
        page_name=page["name"],
        ig_username=ig_account.get("username"),
        access_token_encrypted=encrypt_secret(page["access_token"]),
        is_primary=True,
    )
    db.add(connection)
    await db.commit()
    await db.refresh(connection)
    return connection


def _to_status(connection: MetaConnection) -> MetaConnectionStatus:
    return MetaConnectionStatus(
        connected=True,
        fb_page_id=connection.fb_page_id,
        ig_business_id=connection.ig_business_id,
        page_name=connection.page_name,
        ig_username=connection.ig_username,
        token_expires_at=connection.token_expires_at,
        is_primary=connection.is_primary,
    )


@router.get("/status", response_model=MetaConnectionStatus)
async def status_(
    account_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_business_access),
) -> MetaConnectionStatus:
    result = await db.execute(
        select(MetaConnection)
        .where(MetaConnection.account_id == account_id, MetaConnection.is_primary)
        .order_by(MetaConnection.created_at.desc())
    )
    connection = result.scalars().first()
    if connection is None:
        return MetaConnectionStatus(connected=False)
    return _to_status(connection)


@router.delete("/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(
    account_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_business_access),
) -> None:
    result = await db.execute(
        select(MetaConnection).where(MetaConnection.account_id == account_id, MetaConnection.is_primary)
    )
    for connection in result.scalars().all():
        connection.is_primary = False
    await db.commit()
