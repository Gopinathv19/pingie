"""Shared knowledge: summaries and notes copied across a workspace's bots.

Revision ID: 0006_shared_knowledge
Revises: 0005_live_chat
Create Date: 2026-10-17 00:00:00.000000+00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0006_shared_knowledge"
down_revision: str | None = "0005_live_chat"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("bot_answers", sa.Column("kind", sa.String(16), nullable=False, server_default="answer"))
    op.add_column(
        "bot_answers",
        sa.Column("origin_bot_id", UUID(as_uuid=True), sa.ForeignKey("bots.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column("bot_answers", sa.Column("share_group_id", UUID(as_uuid=True), nullable=True))
    op.create_index("ix_bot_answers_share_group_id", "bot_answers", ["share_group_id"])


def downgrade() -> None:
    op.drop_index("ix_bot_answers_share_group_id", table_name="bot_answers")
    op.drop_column("bot_answers", "share_group_id")
    op.drop_column("bot_answers", "origin_bot_id")
    op.drop_column("bot_answers", "kind")
