import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.account import Account


class MovementType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class IncomeSource(str, enum.Enum):
    MENTORIA = "mentoria"
    COMUNIDAD = "comunidad"
    CLARIDAD = "claridad"
    PRODUCTO = "producto"
    OTRO = "otro"


class PaymentMethod(str, enum.Enum):
    TRANSFERENCIA = "transferencia"
    STRIPE = "stripe"
    MERCADOPAGO = "mercadopago"
    PAYPAL = "paypal"
    EFECTIVO = "efectivo"


class ExpenseCategory(str, enum.Enum):
    HERRAMIENTAS = "herramientas"
    PUBLICIDAD = "publicidad"
    EDUCACION = "educacion"
    SERVICIOS = "servicios"
    OTRO = "otro"


class MoneyMovement(Base):
    """A single income or expense entry for a business, on a specific date.

    Modeled as one table with a `type` discriminator (rather than separate
    incomes/expenses tables) so totals and date-range queries across both don't
    require a UNION. `source`/`payment_method` only apply to incomes and `category`
    only to expenses — enforced by the two distinct request schemas per endpoint
    (app/schemas/money_movement.py), not by a DB constraint.
    """

    __tablename__ = "money_movements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[MovementType] = mapped_column(
        Enum(MovementType, name="movement_type", values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[IncomeSource | None] = mapped_column(
        Enum(IncomeSource, name="income_source", values_callable=lambda obj: [e.value for e in obj]),
        nullable=True,
    )
    payment_method: Mapped[PaymentMethod | None] = mapped_column(
        Enum(PaymentMethod, name="payment_method", values_callable=lambda obj: [e.value for e in obj]),
        nullable=True,
    )
    category: Mapped[ExpenseCategory | None] = mapped_column(
        Enum(ExpenseCategory, name="expense_category", values_callable=lambda obj: [e.value for e in obj]),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    account: Mapped["Account"] = relationship(back_populates="money_movements")
