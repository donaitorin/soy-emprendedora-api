"""add deleted_at to money_movements for soft delete

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-30
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("money_movements", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("money_movements", "deleted_at")
