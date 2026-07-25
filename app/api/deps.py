import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.entitlement import Entitlement, EntitlementStatus
from app.models.user import PlatformRole, User
from app.models.user_account import BusinessRole, UserAccount

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    return user


async def require_platform_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != PlatformRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Platform admin access required")
    return user


async def _get_membership(db: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID) -> UserAccount | None:
    result = await db.execute(
        select(UserAccount).where(UserAccount.user_id == user_id, UserAccount.account_id == account_id)
    )
    return result.scalar_one_or_none()


async def ensure_business_access(user: User, account_id: uuid.UUID, db: AsyncSession) -> None:
    """Core check reused by both the path/query-param dependency below and callers
    that need to validate access to an `account_id` coming from a request body
    (e.g. /meta/select-page), where FastAPI can't auto-inject it into a dependency."""
    if user.role == PlatformRole.ADMIN:
        return
    membership = await _get_membership(db, user.id, account_id)
    if membership is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No access to this business")


async def require_business_access(
    account_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """User must be admin, or have any role on the `account_id` path/query parameter.

    FastAPI resolves `account_id` here from the route's own path or query parameter
    of the same name — this dependency must only be used on routes that declare an
    `account_id` parameter directly (path or query), not one nested in a body.
    """
    await ensure_business_access(user, account_id, db)
    return user


async def require_business_owner(
    account_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """User must be admin, or the `owner` of the `account_id` path parameter."""
    if user.role == PlatformRole.ADMIN:
        return user
    membership = await _get_membership(db, user.id, account_id)
    if membership is None or membership.role != BusinessRole.OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Business owner access required")
    return user


async def check_entitlement(account_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> bool:
    """Centralized entitlement check.

    TODO: activar validación real de entitlement cuando se integre facturación.
    For now, access is free/open regardless of the result below — this function exists
    so that callers (e.g. dashboard routes) already depend on it, and turning on real
    enforcement later is a one-line change here instead of touching every endpoint.
    """
    result = await db.execute(
        select(Entitlement)
        .where(
            Entitlement.account_id == account_id,
            Entitlement.status.in_([EntitlementStatus.ACTIVE, EntitlementStatus.TRIALING]),
        )
        .order_by(Entitlement.created_at.desc())
    )
    _ = result.scalars().first()
    return True
