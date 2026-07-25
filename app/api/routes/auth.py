from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.account import Account
from app.models.entitlement import Entitlement, EntitlementStatus
from app.models.user import User
from app.models.user_account import BusinessRole, UserAccount
from app.schemas.account import AccountWithRole
from app.schemas.auth import LoginRequest, MeResponse, RegisterRequest
from app.schemas.token import TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
    )
    db.add(user)
    await db.flush()

    # Business logic decision (not a DB constraint): a user gets exactly one account
    # on registration today. See app/models/user_account.py for why the schema allows more.
    account = Account(name=f"{payload.first_name} {payload.last_name}".strip())
    db.add(account)
    await db.flush()

    db.add(UserAccount(user_id=user.id, account_id=account.id, role=BusinessRole.OWNER))
    db.add(
        Entitlement(
            account_id=account.id,
            plan="free",
            status=EntitlementStatus.ACTIVE,
            source="manual",
        )
    )
    await db.commit()

    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User is inactive")

    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=MeResponse)
async def get_me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> MeResponse:
    result = await db.execute(
        select(Account, UserAccount.role)
        .join(UserAccount, UserAccount.account_id == Account.id)
        .where(UserAccount.user_id == user.id)
    )
    accounts = [
        AccountWithRole(id=account.id, name=account.name, created_at=account.created_at, my_role=role)
        for account, role in result.all()
    ]

    return MeResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        accounts=accounts,
    )
