import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.db.models.mixins import TimestampCreated, UUIDPrimaryKey


class AllowedDomain(UUIDPrimaryKey, TimestampCreated, Base):
    """A host the widget may load on. `*.acme.com` covers every subdomain."""

    __tablename__ = "allowed_domains"
    __table_args__ = (UniqueConstraint("bot_id", "host", name="uq_allowed_domains_bot_host"),)

    bot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    # Set when the widget loads from this host: the install check.
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
