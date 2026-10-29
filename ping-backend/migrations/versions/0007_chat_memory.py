"""Chat memory: finished conversations pushed to Memora.

Revision ID: 0007_chat_memory
Revises: 0006_shared_knowledge
Create Date: 2026-10-20 00:00:00.000000+00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0007_chat_memory"
down_revision: str | None = "0006_shared_knowledge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("memora_source_id", UUID(as_uuid=True), nullable=True))
    op.add_column("conversations", sa.Column("memory_synced_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("conversations", "memory_synced_at")
    op.drop_column("conversations", "memora_source_id")
