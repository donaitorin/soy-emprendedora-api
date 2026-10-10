"""leads: optional scheduled date/time for a meeting or call

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-10
"""

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "scheduled_at")
