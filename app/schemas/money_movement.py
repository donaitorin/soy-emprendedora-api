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
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    amount: Decimal
    occurred_on: date
    source: IncomeSource
    payment_method: PaymentMethod
    created_at: datetime


class ExpenseCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    occurred_on: date
    category: ExpenseCategory


class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    amount: Decimal
    occurred_on: date
    category: ExpenseCategory
    created_at: datetime
