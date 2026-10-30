"""Per-bot control over learning from conversations, and each chat's memory state.

Revision ID: 0009_memory_mode
Revises: 0008_handoff_mode
Create Date: 2026-10-21 00:00:00.000000+00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_memory_mode"
down_revision: str | None = "0008_handoff_mode"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing bots start on "manual" too: nothing is learned until someone opts in.
    op.add_column("bots", sa.Column("memory_mode", sa.String(16), nullable=False, server_default="manual"))
    op.add_column("conversations", sa.Column("memory_status", sa.String(16), nullable=True))
    # Chats pushed before this setting existed are already learned.
    op.execute("UPDATE conversations SET memory_status = 'learned' WHERE memora_source_id IS NOT NULL")


def downgrade() -> None:
    op.drop_column("conversations", "memory_status")
    op.drop_column("bots", "memory_mode")
