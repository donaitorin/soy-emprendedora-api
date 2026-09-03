"""tasks: to-do items scoped to an account, always "for today"

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-12
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

task_priority = postgresql.ENUM("alta", "media", "baja", name="task_priority")
suggestion_type = postgresql.ENUM("posting_reminder", "unanswered_conversation", name="suggestion_type")


def upgrade() -> None:
    # Don't pre-create the ENUM types here: op.create_table() below already creates
    # each one automatically. See 0001's upgrade() for why doing both raises
    # DuplicateObjectError.
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("priority", task_priority, nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("suggestion_type", suggestion_type, nullable=True),
        sa.Column("conversation_ref", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tasks_account_created", "tasks", ["account_id", "created_at"])


def downgrade() -> None:
    # drop_table() drops each column's ENUM type automatically once the last table
    # using it is gone — no manual .drop() needed (mirrors 0001/0002/0004's downgrade).
    op.drop_index("ix_tasks_account_created", table_name="tasks")
    op.drop_table("tasks")
