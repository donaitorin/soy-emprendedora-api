import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_platform_admin
from app.db.session import get_db
from app.models.account import Account
from app.models.entitlement import Entitlement
from app.models.user import PlatformRole, User
from app.schemas.account import AccountRead, AccountUpdate
from app.schemas.entitlement import EntitlementCreate, EntitlementRead, EntitlementUpdate
from app.schemas.user import UserRead, UserUpdateAdmin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_platform_admin)])


@router.get("/users", response_model=list[UserRead])
async def list_users(
    db: AsyncSession = Depends(get_db),
    role: PlatformRole | None = Query(None),
    is_active: bool | None = Query(None),
) -> list[User]:
    stmt = select(User)
    if role is not None:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user(user_id: uuid.UUID, payload: UserUpdateAdmin, db: AsyncSession = Depends(get_db)) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user


@router.get("/accounts", response_model=list[AccountRead])
async def list_accounts(db: AsyncSession = Depends(get_db)) -> list[Account]:
    result = await db.execute(select(Account))
    return list(result.scalars().all())


@router.patch("/accounts/{account_id}", response_model=AccountRead)
async def update_account(
    account_id: uuid.UUID, payload: AccountUpdate, db: AsyncSession = Depends(get_db)
) -> Account:
    account = await db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found")
    if payload.name is not None:
        account.name = payload.name
    await db.commit()
    await db.refresh(account)
    return account


@router.get("/accounts/{account_id}/entitlement", response_model=list[EntitlementRead])
async def get_account_entitlements(account_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[Entitlement]:
    result = await db.execute(
        select(Entitlement).where(Entitlement.account_id == account_id).order_by(Entitlement.created_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/accounts/{account_id}/entitlement", response_model=EntitlementRead, status_code=status.HTTP_201_CREATED
)
async def create_entitlement(
    account_id: uuid.UUID, payload: EntitlementCreate, db: AsyncSession = Depends(get_db)
) -> Entitlement:
    account = await db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found")

    entitlement = Entitlement(account_id=account_id, **payload.model_dump())
    db.add(entitlement)
    await db.commit()
    await db.refresh(entitlement)
    return entitlement


@router.patch("/entitlements/{entitlement_id}", response_model=EntitlementRead)
async def update_entitlement(
    entitlement_id: uuid.UUID, payload: EntitlementUpdate, db: AsyncSession = Depends(get_db)
) -> Entitlement:
    entitlement = await db.get(Entitlement, entitlement_id)
    if entitlement is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entitlement not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entitlement, field, value)

    await db.commit()
    await db.refresh(entitlement)
    return entitlement
