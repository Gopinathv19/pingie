"""Plans table, seeded with the free / pro / enterprise tiers.

Revision ID: 0003_plans
Revises: 0002_pro_enterprise
Create Date: 2026-10-13 00:00:00.000000+00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0003_plans"
down_revision: str | None = "0002_pro_enterprise"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEED = [
    {
        "key": "free", "name": "Free", "description": "For trying Pingie on one site.",
        "price_monthly": 0, "price_label": "$0",
        "messages_limit": 100, "bots_limit": 3, "sources_limit": 5, "members_limit": 1,
        "remove_branding": False, "model_tiers": ["fast"],
        "features": ["3 bots", "100 messages / month", "5 sources per bot", "1 team member", "Fast model tier"],
        "is_public": True, "is_default": True, "highlighted": False, "sort_order": 0,
    },
    {
        "key": "pro", "name": "Pro", "description": "For growing teams running support at scale.",
        "price_monthly": 49, "price_label": "$49",
        "messages_limit": 100_000, "bots_limit": 10, "sources_limit": 25, "members_limit": 5,
        "remove_branding": True, "model_tiers": ["fast", "balanced"],
        "features": [
            "10 bots", "100,000 messages / month", "25 sources per bot", "5 team members",
            "Remove “Powered by Pingie” badge", "Fast + Balanced model tiers",
        ],
        "is_public": True, "is_default": False, "highlighted": True, "sort_order": 10,
    },
    {
        "key": "enterprise", "name": "Enterprise", "description": "Custom limits, security and support.",
        "price_monthly": None, "price_label": "Custom",
        "messages_limit": 10_000_000, "bots_limit": 9999, "sources_limit": 9999, "members_limit": 9999,
        "remove_branding": True, "model_tiers": ["fast", "balanced", "best"],
        "features": [
            "Unlimited bots & messages", "All model tiers", "Unlimited team members",
            "Dedicated Slack support", "SLA & uptime guarantee",
        ],
        "is_public": True, "is_default": False, "highlighted": False, "sort_order": 20,
    },
]


def upgrade() -> None:
    plans = op.create_table(
        "plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("key", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("price_monthly", sa.Integer(), nullable=True),
        sa.Column("price_label", sa.String(40), nullable=False, server_default=""),
        sa.Column("messages_limit", sa.Integer(), nullable=False),
        sa.Column("bots_limit", sa.Integer(), nullable=False),
        sa.Column("sources_limit", sa.Integer(), nullable=False),
        sa.Column("members_limit", sa.Integer(), nullable=False),
        sa.Column("remove_branding", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("model_tiers", JSONB(), nullable=False, server_default='["fast"]'),
        sa.Column("features", JSONB(), nullable=False, server_default="[]"),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("highlighted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.bulk_insert(plans, SEED)


def downgrade() -> None:
    op.drop_table("plans")
