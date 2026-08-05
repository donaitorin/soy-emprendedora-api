"""leads: kanban board entries scoped to an account

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-30
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

lead_channel = postgresql.ENUM(
    "instagram", "whatsapp", "referido", "web", "otro", name="lead_channel"
)
lead_stage = postgresql.ENUM(
    "nuevo", "conversacion", "propuesta", "agendada", "convertida", name="lead_stage"
)
archive_reason = postgresql.ENUM("converted", "not_converted", name="archive_reason")


def upgrade() -> None:
    # Don't pre-create the ENUM types here: op.create_table() below already creates
    # each one automatically. See 0001's upgrade() for why doing both raises
    # DuplicateObjectError.
    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("channel", lead_channel, nullable=False),
        sa.Column("stage", lead_stage, nullable=False, server_default="nuevo"),
        sa.Column("stage_changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("archive_reason", archive_reason, nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_leads_account_archived_stage", "leads", ["account_id", "archived", "stage"])
    op.create_index("ix_leads_account_created", "leads", ["account_id", "created_at"])


def downgrade() -> None:
    # drop_table() drops each column's ENUM type automatically once the last table
    # using it is gone — no manual .drop() needed (mirrors 0001/0002's downgrade).
    op.drop_index("ix_leads_account_created", table_name="leads")
    op.drop_index("ix_leads_account_archived_stage", table_name="leads")
    op.drop_table("leads")
