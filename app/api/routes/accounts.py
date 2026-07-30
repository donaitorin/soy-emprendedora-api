import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_business_access, require_business_owner
from app.core.security import hash_password
from app.db.session import get_db
from app.models.account import Account
from app.models.money_movement import MoneyMovement, MovementType
from app.models.user import User
from app.models.user_account import BusinessRole, UserAccount
from app.schemas.account import AccountRead, AccountUpdate, AccountWithRole
from app.schemas.money_movement import ExpenseCreate, ExpenseRead, IncomeCreate, IncomeRead
from app.schemas.user_account import MemberCreate, MemberRead

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("/me", response_model=list[AccountWithRole])
async def list_my_accounts(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[AccountWithRole]:
    result = await db.execute(
        select(Account, UserAccount.role)
        .join(UserAccount, UserAccount.account_id == Account.id)
        .where(UserAccount.user_id == user.id)
    )
    return [
        AccountWithRole(id=account.id, name=account.name, created_at=account.created_at, my_role=role)
        for account, role in result.all()
    ]


async def _get_account_or_404(db: AsyncSession, account_id: uuid.UUID) -> Account:
    account = await db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found")
    return account


@router.get("/{account_id}", response_model=AccountRead)
async def get_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_business_access),
) -> Account:
    return await _get_account_or_404(db, account_id)


@router.patch("/{account_id}", response_model=AccountRead)
async def update_account(
    account_id: uuid.UUID,
    payload: AccountUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_business_owner),
) -> Account:
    account = await _get_account_or_404(db, account_id)
    if payload.name is not None:
        account.name = payload.name
    await db.commit()
    await db.refresh(account)
    return account


@router.get("/{account_id}/members", response_model=list[MemberRead])
async def list_members(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_business_access),
) -> list[MemberRead]:
    result = await db.execute(
        select(User, UserAccount.role, UserAccount.created_at)
        .join(UserAccount, UserAccount.user_id == User.id)
        .where(UserAccount.account_id == account_id)
    )
    return [
        MemberRead(
            user_id=member.id,
            email=member.email,
            first_name=member.first_name,
            last_name=member.last_name,
            role=role,
            created_at=created_at,
        )
        for member, role, created_at in result.all()
    ]


@router.post("/{account_id}/members", response_model=MemberRead, status_code=status.HTTP_201_CREATED)
async def add_member(
    account_id: uuid.UUID,
    payload: MemberCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_business_owner),
) -> MemberRead:
    await _get_account_or_404(db, account_id)

    result = await db.execute(select(User).where(User.email == payload.email))
    member = result.scalar_one_or_none()

    if member is None:
        # TODO: reemplazar por flujo de invitación por email. Por ahora se crea el
        # usuario con una contraseña temporal aleatoria; no se le notifica nada.
        import secrets

        temp_password = secrets.token_urlsafe(16)
        member = User(
            email=payload.email,
            password_hash=hash_password(temp_password),
            first_name="Pendiente",
            last_name="Pendiente",
        )
        db.add(member)
        await db.flush()
    else:
        existing = await db.execute(
            select(UserAccount).where(
                UserAccount.user_id == member.id, UserAccount.account_id == account_id
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "User is already a member of this business")

    user_account = UserAccount(user_id=member.id, account_id=account_id, role=BusinessRole.COLLABORATOR)
    db.add(user_account)
    await db.commit()

    return MemberRead(
        user_id=member.id,
        email=member.email,
        first_name=member.first_name,
        last_name=member.last_name,
        role=BusinessRole.COLLABORATOR,
        created_at=user_account.created_at,
    )


@router.delete("/{account_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    account_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_business_owner),
) -> None:
    result = await db.execute(
        select(UserAccount).where(UserAccount.user_id == user_id, UserAccount.account_id == account_id)
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")

    if membership.role == BusinessRole.OWNER:
        owners_count = await db.execute(
            select(UserAccount).where(
                UserAccount.account_id == account_id, UserAccount.role == BusinessRole.OWNER
            )
        )
        if len(owners_count.scalars().all()) <= 1:
            raise HTTPException(status.HTTP_409_CONFLICT, "Cannot remove the only owner of a business")

    await db.delete(membership)
    await db.commit()


async def _list_movements(
    db: AsyncSession, account_id: uuid.UUID, movement_type: MovementType, from_: date | None, to: date | None
) -> list[MoneyMovement]:
    stmt = select(MoneyMovement).where(
        MoneyMovement.account_id == account_id, MoneyMovement.type == movement_type
    )
    if from_ is not None:
        stmt = stmt.where(MoneyMovement.occurred_on >= from_)
    if to is not None:
        stmt = stmt.where(MoneyMovement.occurred_on <= to)
    stmt = stmt.order_by(MoneyMovement.occurred_on.desc(), MoneyMovement.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/{account_id}/incomes", response_model=IncomeRead, status_code=status.HTTP_201_CREATED)
async def create_income(
    account_id: uuid.UUID,
    payload: IncomeCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_business_access),
) -> MoneyMovement:
    await _get_account_or_404(db, account_id)

    movement = MoneyMovement(
        account_id=account_id,
        type=MovementType.INCOME,
        amount=payload.amount,
        occurred_on=payload.occurred_on,
        source=payload.source,
        payment_method=payload.payment_method,
    )
    db.add(movement)
    await db.commit()
    await db.refresh(movement)
    return movement


@router.get("/{account_id}/incomes", response_model=list[IncomeRead])
async def list_incomes(
    account_id: uuid.UUID,
    from_: date | None = Query(None, alias="from"),
    to: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_business_access),
) -> list[MoneyMovement]:
    return await _list_movements(db, account_id, MovementType.INCOME, from_, to)


@router.post("/{account_id}/expenses", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
async def create_expense(
    account_id: uuid.UUID,
    payload: ExpenseCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_business_access),
) -> MoneyMovement:
    await _get_account_or_404(db, account_id)

    movement = MoneyMovement(
        account_id=account_id,
        type=MovementType.EXPENSE,
        amount=payload.amount,
        occurred_on=payload.occurred_on,
        category=payload.category,
    )
    db.add(movement)
    await db.commit()
    await db.refresh(movement)
    return movement


@router.get("/{account_id}/expenses", response_model=list[ExpenseRead])
async def list_expenses(
    account_id: uuid.UUID,
    from_: date | None = Query(None, alias="from"),
    to: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_business_access),
) -> list[MoneyMovement]:
    return await _list_movements(db, account_id, MovementType.EXPENSE, from_, to)
