"""Per-bot handoff mode: how the bot reacts when a visitor asks for a person.

Revision ID: 0008_handoff_mode
Revises: 0007_chat_memory
Create Date: 2026-10-20 00:00:00.000000+00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_handoff_mode"
down_revision: str | None = "0007_chat_memory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("bots", sa.Column("handoff_mode", sa.String(16), nullable=False, server_default="offer"))


def downgrade() -> None:
    op.drop_column("bots", "handoff_mode")
