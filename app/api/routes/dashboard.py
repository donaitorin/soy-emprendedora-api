import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import check_entitlement, require_business_access
from app.core.security import decrypt_secret
from app.db.session import get_db
from app.models.meta_connection import MetaConnection
from app.schemas.dashboard import DashboardInsights, PostingStatus, UnansweredConversation
from app.services import meta_client

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


async def _get_active_connection_or_404(db: AsyncSession, account_id: uuid.UUID) -> MetaConnection:
    result = await db.execute(
        select(MetaConnection)
        .where(MetaConnection.account_id == account_id, MetaConnection.is_primary)
        .order_by(MetaConnection.created_at.desc())
    )
    connection = result.scalars().first()
    if connection is None or connection.ig_business_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No active Meta/Instagram connection for this business")
    return connection


@router.get("/{account_id}/insights", response_model=DashboardInsights)
async def get_insights(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _access=Depends(require_business_access),
    _entitled: bool = Depends(check_entitlement),
) -> DashboardInsights:
    connection = await _get_active_connection_or_404(db, account_id)

    page_access_token = decrypt_secret(connection.access_token_encrypted)
    try:
        insights = await meta_client.get_ig_insights(connection.ig_business_id, page_access_token)
    except meta_client.MetaAPIError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Meta Graph API error: {exc}")

    return DashboardInsights(ig_business_id=connection.ig_business_id, **insights)


@router.get("/{account_id}/posting-status", response_model=PostingStatus)
async def get_posting_status(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _access=Depends(require_business_access),
    _entitled: bool = Depends(check_entitlement),
) -> PostingStatus:
    connection = await _get_active_connection_or_404(db, account_id)

    page_access_token = decrypt_secret(connection.access_token_encrypted)
    try:
        posting_status = await meta_client.get_ig_posting_status(connection.ig_business_id, page_access_token)
    except meta_client.MetaAPIError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Meta Graph API error: {exc}")

    return PostingStatus(**posting_status)


@router.get("/{account_id}/unanswered-conversations", response_model=list[UnansweredConversation])
async def get_unanswered_conversations(
    account_id: uuid.UUID,
    limit: int = Query(2, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _access=Depends(require_business_access),
    _entitled: bool = Depends(check_entitlement),
) -> list[UnansweredConversation]:
    connection = await _get_active_connection_or_404(db, account_id)

    page_access_token = decrypt_secret(connection.access_token_encrypted)
    try:
        conversations = await meta_client.get_ig_unanswered_conversations(
            connection.fb_page_id, connection.ig_business_id, page_access_token, limit=limit
        )
    except meta_client.MetaAPIError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Meta Graph API error: {exc}")

    return [UnansweredConversation(**c) for c in conversations]
