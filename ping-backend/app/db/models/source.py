import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.db.models.mixins import TimestampCreated, UUIDPrimaryKey


class BotSource(UUIDPrimaryKey, TimestampCreated, Base):
    """A knowledge source as the dashboard shows it.

    Files and single pages map to exactly one Memora source. A sitemap is a
    parent row with one child row (type `page`) per crawled page; the parent
    carries the aggregate status and chunk count, children are not listed.
    """

    __tablename__ = "bot_sources"
    __table_args__ = (
        Index("ix_bot_sources_bot_parent", "bot_id", "parent_id"),
        Index("ix_bot_sources_status", "status"),
    )

    bot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bots.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bot_sources.id", ondelete="CASCADE"), nullable=True
    )
    memora_source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # pdf | docx | text | url | sitemap | page
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(1024), nullable=False)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    # queued | indexing | ready | failed
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="queued")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
