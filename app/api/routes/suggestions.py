import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_business_access
from app.db.session import get_db
from app.models.account import Account
from app.models.suggestion import Suggestion
from app.models.user import User
from app.schemas.suggestion import SuggestionCreate, SuggestionRead

router = APIRouter(prefix="/accounts", tags=["suggestions"])


@router.post("/{account_id}/suggestions", response_model=SuggestionRead, status_code=status.HTTP_201_CREATED)
async def create_suggestion(
    account_id: uuid.UUID,
    payload: SuggestionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_business_access),
) -> Suggestion:
    if await db.get(Account, account_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Business not found")

    suggestion = Suggestion(account_id=account_id, user_id=user.id, message=payload.message)
    db.add(suggestion)
    await db.commit()
    await db.refresh(suggestion)
    return suggestion
