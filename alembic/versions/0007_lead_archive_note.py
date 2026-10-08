"""leads: optional markdown note when archiving as not_converted

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-08
"""

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("archive_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "archive_note")
