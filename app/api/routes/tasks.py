import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_business_access
from app.db.session import get_db
from app.models.account import Account
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate

router = APIRouter(prefix="/accounts", tags=["tasks"])


async def _get_account_or_404(db: AsyncSession, account_id: uuid.UUID) -> Account:
    account = await db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found")
    return account


@router.post("/{account_id}/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    account_id: uuid.UUID,
    payload: TaskCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_business_access),
) -> Task:
    await _get_account_or_404(db, account_id)

    task = Task(
        account_id=account_id,
        title=payload.title,
        notes=payload.notes,
        priority=payload.priority,
        suggestion_type=payload.suggestion_type,
        conversation_ref=payload.conversation_ref,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.get("/{account_id}/tasks", response_model=list[TaskRead])
async def list_tasks(
    account_id: uuid.UUID,
    date_: date | None = Query(None, alias="date"),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_business_access),
) -> list[Task]:
    """Tasks for one day — unpaginated, always few. `date` defaults to today in UTC,
    but the frontend is expected to always pass it explicitly (computed in the
    browser's own timezone) rather than rely on the server's notion of "today"."""
    target_date = date_ or datetime.now(UTC).date()
    result = await db.execute(
        select(Task)
        .where(Task.account_id == account_id, func.date(Task.created_at) == target_date)
        .order_by(Task.created_at.desc())
    )
    return list(result.scalars().all())


@router.patch("/{account_id}/tasks/{task_id}", response_model=TaskRead)
async def update_task(
    account_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_business_access),
) -> Task:
    result = await db.execute(select(Task).where(Task.id == task_id, Task.account_id == account_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")

    task.done = payload.done
    await db.commit()
    await db.refresh(task)
    return task
