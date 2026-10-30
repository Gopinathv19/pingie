"""Widget upgrade: chat ratings, the Help Center, and custom design for paid plans.

Revision ID: 0011_widget_upgrade
Revises: 0010_bot_controls
Create Date: 2026-10-21 12:00:00.000000+00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_widget_upgrade"
down_revision: str | None = "0010_bot_controls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Chat satisfaction: 1 unhappy, 2 neutral, 3 happy.
    op.add_column("conversations", sa.Column("csat", sa.SmallInteger(), nullable=True))
    op.add_column("conversations", sa.Column("csat_comment", sa.Text(), nullable=False, server_default=""))
    op.add_column("conversations", sa.Column("csat_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("conversations", sa.Column("csat_source", sa.String(16), nullable=True))

    # Help Center: a readable copy of web pages and small text uploads.
    op.add_column("bot_sources", sa.Column("title", sa.String(300), nullable=False, server_default=""))
    op.add_column("bot_sources", sa.Column("content", sa.Text(), nullable=True))
    op.add_column("bot_sources", sa.Column("in_help_center", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("bot_sources", sa.Column("helpful_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("bot_sources", sa.Column("unhelpful_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("bot_answers", sa.Column("in_help_center", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("bot_answers", sa.Column("helpful_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("bot_answers", sa.Column("unhelpful_count", sa.Integer(), nullable=False, server_default="0"))

    # Custom widget design is a paid-plan feature, copied plan -> org like branding.
    op.add_column("plans", sa.Column("custom_design", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("organizations", sa.Column("custom_design", sa.Boolean(), nullable=False, server_default="false"))
    op.execute("UPDATE plans SET custom_design = true WHERE key <> 'free'")
    op.execute(
        "UPDATE organizations o SET custom_design = p.custom_design FROM plans p WHERE p.key = o.plan"
    )


def downgrade() -> None:
    op.drop_column("organizations", "custom_design")
    op.drop_column("plans", "custom_design")
    for col in ("unhelpful_count", "helpful_count", "in_help_center"):
        op.drop_column("bot_answers", col)
    for col in ("unhelpful_count", "helpful_count", "in_help_center", "content", "title"):
        op.drop_column("bot_sources", col)
    for col in ("csat_source", "csat_at", "csat_comment", "csat"):
        op.drop_column("conversations", col)
