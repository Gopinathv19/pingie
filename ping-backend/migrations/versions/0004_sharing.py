"""Bot sharing, workspace invitations, and a per-plan shares limit.

Revision ID: 0004_sharing
Revises: 0003_plans
Create Date: 2026-10-13 00:00:00.000000+00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0004_sharing"
down_revision: str | None = "0003_plans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_pk() -> sa.Column:
    return sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"))


def _created() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    op.add_column("plans", sa.Column("shares_limit", sa.Integer(), nullable=False, server_default="3"))
    op.add_column("organizations", sa.Column("shares_limit", sa.Integer(), nullable=False, server_default="3"))
    op.execute("UPDATE plans SET shares_limit = 9999 WHERE key <> 'free'")
    op.execute(
        "UPDATE organizations o SET shares_limit = p.shares_limit FROM plans p WHERE p.key = o.plan"
    )

    op.create_table(
        "bot_shares",
        _uuid_pk(),
        sa.Column("bot_id", UUID(as_uuid=True), sa.ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("invited_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        _created(),
        sa.UniqueConstraint("bot_id", "user_id", name="uq_bot_share"),
    )

    op.create_table(
        "invitations",
        _uuid_pk(),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(320), nullable=False, index=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column(
            "organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("bot_id", UUID(as_uuid=True), sa.ForeignKey("bots.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("invited_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        _created(),
    )


def downgrade() -> None:
    op.drop_table("invitations")
    op.drop_table("bot_shares")
    op.drop_column("organizations", "shares_limit")
    op.drop_column("plans", "shares_limit")
