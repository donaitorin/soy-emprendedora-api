"""leads: one attached PDF per lead (object key + metadata)

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-11
"""

import sqlalchemy as sa

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("pdf_key", sa.Text(), nullable=True))
    op.add_column("leads", sa.Column("pdf_filename", sa.Text(), nullable=True))
    op.add_column("leads", sa.Column("pdf_size", sa.Integer(), nullable=True))
    op.add_column("leads", sa.Column("pdf_uploaded_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "pdf_uploaded_at")
    op.drop_column("leads", "pdf_size")
    op.drop_column("leads", "pdf_filename")
    op.drop_column("leads", "pdf_key")
