"""Bot controls: answer strictness, staying on topic, business hours, alerts,
and saved replies for agents.

Revision ID: 0010_bot_controls
Revises: 0009_memory_mode
Create Date: 2026-10-21 00:00:00.000000+00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0010_bot_controls"
down_revision: str | None = "0009_memory_mode"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("bots", sa.Column("answer_strictness", sa.String(16), nullable=False, server_default="balanced"))
    op.add_column("bots", sa.Column("topic_guard", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("bots", sa.Column("blocked_topics", sa.Text(), nullable=False, server_default=""))
    op.add_column("bots", sa.Column("off_topic_message", sa.Text(), nullable=False, server_default=""))
    op.add_column("bots", sa.Column("business_hours", JSONB(), nullable=False, server_default="{}"))
    op.add_column("bots", sa.Column("alert_slack_url", sa.String(512), nullable=False, server_default=""))
    op.add_column("bots", sa.Column("alert_webhook_url", sa.String(512), nullable=False, server_default=""))
    op.add_column(
        "bots",
        sa.Column("alert_events", JSONB(), nullable=False, server_default='["wants_person", "lead", "disliked"]'),
    )
    op.create_table(
        "bot_saved_replies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("bot_id", UUID(as_uuid=True), sa.ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("bot_saved_replies")
    for col in (
        "alert_events", "alert_webhook_url", "alert_slack_url", "business_hours",
        "off_topic_message", "blocked_topics", "topic_guard", "answer_strictness",
    ):
        op.drop_column("bots", col)
