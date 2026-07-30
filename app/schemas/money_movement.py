import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.money_movement import ExpenseCategory, IncomeSource, PaymentMethod


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
