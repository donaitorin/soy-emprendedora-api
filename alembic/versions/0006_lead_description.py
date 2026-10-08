"""leads: optional markdown description

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-08
"""

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "description")
