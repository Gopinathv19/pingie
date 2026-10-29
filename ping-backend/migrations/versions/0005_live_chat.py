"""Live chat: conversation status and assignee, agent messages, presence,
and answers taught from the inbox.

Revision ID: 0005_live_chat
Revises: 0004_sharing
Create Date: 2026-10-14 00:00:00.000000+00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0005_live_chat"
down_revision: str | None = "0004_sharing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("status", sa.String(16), nullable=False, server_default="bot"))
    op.add_column(
        "conversations",
        sa.Column("assigned_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column("conversations", sa.Column("handoff_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("conversations", sa.Column("agent_joined_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_conversations_bot_status", "conversations", ["bot_id", "status"])

    op.add_column(
        "messages",
        sa.Column("author_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column("bots", sa.Column("faq_source_id", UUID(as_uuid=True), nullable=True))

    op.create_table(
        "agent_presence",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("available", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "bot_answers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("bot_id", UUID(as_uuid=True), sa.ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("bot_answers")
    op.drop_table("agent_presence")
    op.drop_column("bots", "faq_source_id")
    op.drop_column("messages", "author_user_id")
    op.drop_index("ix_conversations_bot_status", table_name="conversations")
    op.drop_column("conversations", "agent_joined_at")
    op.drop_column("conversations", "handoff_requested_at")
    op.drop_column("conversations", "assigned_user_id")
    op.drop_column("conversations", "status")
