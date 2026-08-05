import math
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_business_access
from app.db.session import get_db
from app.models.account import Account
from app.models.lead import ArchiveReason, Lead, LeadStage
from app.schemas.lead import (
    LeadArchiveRequest,
    LeadCreate,
    LeadPage,
    LeadRead,
    LeadStageUpdate,
    LeadStats,
)

router = APIRouter(prefix="/accounts", tags=["leads"])


async def _get_account_or_404(db: AsyncSession, account_id: uuid.UUID) -> Account:
    account = await db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found")
    return account


async def _get_active_lead_or_404(db: AsyncSession, account_id: uuid.UUID, lead_id: uuid.UUID) -> Lead:
    """A lead usable from the board: not archived, not soft-deleted."""
    result = await db.execute(
        select(Lead).where(
            Lead.id == lead_id,
            Lead.account_id == account_id,
            Lead.archived.is_(False),
            Lead.deleted_at.is_(None),
        )
    )
    lead = result.scalar_one_or_none()
    if lead is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")
    return lead


@router.post("/{account_id}/leads", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
async def create_lead(
    account_id: uuid.UUID,
    payload: LeadCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_business_access),
) -> Lead:
    await _get_account_or_404(db, account_id)

    lead = Lead(account_id=account_id, name=payload.name, channel=payload.channel, stage=LeadStage.NUEVO)
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return lead


@router.get("/{account_id}/leads", response_model=LeadPage)
async def list_leads(
    account_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    stage: LeadStage | None = Query(None),
    archived: bool | None = Query(None),
    archive_reason: ArchiveReason | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_business_access),
) -> LeadPage:
    """Paginated table of all leads (active + archived, never soft-deleted) —
    same page/page_size/total/total_pages shape as GET /accounts/{id}/movements."""
    filters = [Lead.account_id == account_id, Lead.deleted_at.is_(None)]
    if stage is not None:
        filters.append(Lead.stage == stage)
    if archived is not None:
        filters.append(Lead.archived.is_(archived))
    if archive_reason is not None:
        filters.append(Lead.archive_reason == archive_reason)

    total = (await db.execute(select(func.count()).select_from(Lead).where(*filters))).scalar_one()

    stmt = (
        select(Lead)
        .where(*filters)
        .order_by(Lead.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = (await db.execute(stmt)).scalars().all()

    return LeadPage(
        items=[LeadRead.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{account_id}/leads/board", response_model=list[LeadRead])
async def get_board(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_business_access),
) -> list[Lead]:
    """Raw, unpaginated data for the kanban board: active leads only (not archived,
    not soft-deleted). The frontend groups these by `stage` into columns."""
    result = await db.execute(
        select(Lead)
        .where(Lead.account_id == account_id, Lead.archived.is_(False), Lead.deleted_at.is_(None))
        .order_by(Lead.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{account_id}/leads/stats", response_model=LeadStats)
async def get_stats(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_business_access),
) -> LeadStats:
    base_filters = (Lead.account_id == account_id, Lead.deleted_at.is_(None))

    active_count = (
        await db.execute(
            select(func.count()).select_from(Lead).where(*base_filters, Lead.archived.is_(False))
        )
    ).scalar_one()

    # "Convertidos" = archived with reason=converted, OR still active and sitting in
    # the "convertida" column (not archived yet). Fetched as full rows (not just a
    # count) because avg_conversion_days needs each row's converted_at/created_at.
    converted_result = await db.execute(
        select(Lead).where(
            *base_filters,
            or_(
                and_(Lead.archived.is_(True), Lead.archive_reason == ArchiveReason.CONVERTED),
                and_(Lead.archived.is_(False), Lead.stage == LeadStage.CONVERTIDA),
            ),
        )
    )
    converted_leads = list(converted_result.scalars().all())

    not_converted_count = (
        await db.execute(
            select(func.count())
            .select_from(Lead)
            .where(*base_filters, Lead.archived.is_(True), Lead.archive_reason == ArchiveReason.NOT_CONVERTED)
        )
    ).scalar_one()

    denominator = len(converted_leads) + not_converted_count
    conversion_rate = round(len(converted_leads) / denominator, 4) if denominator > 0 else None

    conversion_days = [
        (lead.converted_at - lead.created_at).total_seconds() / 86400
        for lead in converted_leads
        if lead.converted_at is not None
    ]
    avg_conversion_days = round(sum(conversion_days) / len(conversion_days), 1) if conversion_days else None

    return LeadStats(
        active_count=active_count, conversion_rate=conversion_rate, avg_conversion_days=avg_conversion_days
    )


@router.post("/{account_id}/leads/archive-converted", response_model=list[LeadRead])
async def archive_converted_leads(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_business_access),
) -> list[Lead]:
    """Archives every active lead currently in the 'convertida' column, with
    `archive_reason` forced to 'converted' — the "Archivar convertidos" button.
    Equivalent to calling POST /leads/{id}/archive once per lead in that column,
    but atomic and in one round-trip."""
    result = await db.execute(
        select(Lead).where(
            Lead.account_id == account_id,
            Lead.stage == LeadStage.CONVERTIDA,
            Lead.archived.is_(False),
            Lead.deleted_at.is_(None),
        )
    )
    leads = list(result.scalars().all())

    now = datetime.now(UTC)
    for lead in leads:
        lead.archived = True
        lead.archive_reason = ArchiveReason.CONVERTED
        lead.archived_at = now

    await db.commit()
    for lead in leads:
        await db.refresh(lead)
    return leads


@router.patch("/{account_id}/leads/{lead_id}/stage", response_model=LeadRead)
async def update_lead_stage(
    account_id: uuid.UUID,
    lead_id: uuid.UUID,
    payload: LeadStageUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_business_access),
) -> Lead:
    lead = await _get_active_lead_or_404(db, account_id, lead_id)

    lead.stage = payload.stage
    lead.stage_changed_at = datetime.now(UTC)

    if payload.stage == LeadStage.CONVERTIDA:
        if lead.converted_at is None:
            lead.converted_at = datetime.now(UTC)
    else:
        # Moving away from "convertida" means it no longer counts as converted —
        # otherwise re-entering the column later wouldn't refresh converted_at
        # (the rule above only sets it when it's still null).
        lead.converted_at = None

    await db.commit()
    await db.refresh(lead)
    return lead


@router.post("/{account_id}/leads/{lead_id}/archive", response_model=LeadRead)
async def archive_lead(
    account_id: uuid.UUID,
    lead_id: uuid.UUID,
    payload: LeadArchiveRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_business_access),
) -> Lead:
    lead = await _get_active_lead_or_404(db, account_id, lead_id)

    lead.archived = True
    lead.archive_reason = payload.reason
    lead.archived_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(lead)
    return lead


@router.delete("/{account_id}/leads/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    account_id: uuid.UUID,
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_business_access),
) -> None:
    """Soft-deletes a lead (active or archived) — same pattern as
    DELETE /accounts/{id}/movements/{id}. Excluded from board, table, and stats."""
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.account_id == account_id, Lead.deleted_at.is_(None))
    )
    lead = result.scalar_one_or_none()
    if lead is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")

    lead.deleted_at = datetime.now(UTC)
    await db.commit()
