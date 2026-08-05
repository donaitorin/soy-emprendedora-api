import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.money_movement import ExpenseCategory, IncomeSource, MovementType, PaymentMethod


class IncomeCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    occurred_on: date
    source: IncomeSource
    payment_method: PaymentMethod


class IncomeRead(BaseModel):
    """`amount` is float here (not Decimal) on purpose: Pydantic v2 serializes Decimal
    as a JSON string to avoid precision loss, but that breaks naive `total += amount`
    arithmetic on the frontend. Storage keeps NUMERIC/Decimal (see MoneyMovement) —
    this is only about the shape of the HTTP response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    amount: float
    occurred_on: date
    source: IncomeSource
    payment_method: PaymentMethod
    created_at: datetime


class ExpenseCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    occurred_on: date
    category: ExpenseCategory


class ExpenseRead(BaseModel):
    """See IncomeRead's docstring for why `amount` is float here, not Decimal."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    amount: float
    occurred_on: date
    category: ExpenseCategory
    created_at: datetime


class MovementRead(BaseModel):
    """Combined income/expense view for the mixed, paginated movements table.

    Always exposes every field (income-only and expense-only alike), null when not
    applicable to this row's `type` — same pattern as MetaConnectionStatus, which
    always exposes every connection field even when there's no active connection."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    type: MovementType
    amount: float
    occurred_on: date
    created_at: datetime
    source: IncomeSource | None
    payment_method: PaymentMethod | None
    category: ExpenseCategory | None


class MovementPage(BaseModel):
    items: list[MovementRead]
    page: int
    page_size: int
    total: int
    total_pages: int
