"""Add pro/enterprise plan limit columns to organizations.

Revision ID: 0002_pro_enterprise
Revises: 0001_initial
Create Date: 2026-10-13 00:00:00.000000+00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_pro_enterprise"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("sources_limit", sa.Integer(), nullable=False, server_default="5"))
    op.add_column("organizations", sa.Column("members_limit", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("organizations", sa.Column("remove_branding", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("organizations", sa.Column("stripe_customer_id", sa.String(length=64), nullable=True))
    op.add_column("organizations", sa.Column("stripe_subscription_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "stripe_subscription_id")
    op.drop_column("organizations", "stripe_customer_id")
    op.drop_column("organizations", "remove_branding")
    op.drop_column("organizations", "members_limit")
    op.drop_column("organizations", "sources_limit")
