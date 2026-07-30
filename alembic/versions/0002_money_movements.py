"""money movements: single table with a type discriminator for incomes and expenses

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-29
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

movement_type = postgresql.ENUM("income", "expense", name="movement_type")
income_source = postgresql.ENUM("mentoria", "comunidad", "claridad", "producto", "otro", name="income_source")
payment_method = postgresql.ENUM(
    "transferencia", "stripe", "mercadopago", "paypal", "efectivo", name="payment_method"
)
expense_category = postgresql.ENUM(
    "herramientas", "publicidad", "educacion", "servicios", "otro", name="expense_category"
)


def upgrade() -> None:
    # Don't pre-create the ENUM types here: op.create_table() below already creates
    # each one automatically (via the column's postgresql.ENUM type). See 0001 for why
    # doing both raises DuplicateObjectError.
    op.create_table(
        "money_movements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", movement_type, nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("source", income_source, nullable=True),
        sa.Column("payment_method", payment_method, nullable=True),
        sa.Column("category", expense_category, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_money_movements_account_type_occurred",
        "money_movements",
        ["account_id", "type", "occurred_on"],
    )


def downgrade() -> None:
    # drop_table() drops each column's ENUM type automatically once the last table
    # using it is gone — no manual .drop() needed (mirrors 0001's downgrade).
    op.drop_index("ix_money_movements_account_type_occurred", table_name="money_movements")
    op.drop_table("money_movements")
