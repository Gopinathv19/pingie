import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.db.models.mixins import TimestampCreated, UUIDPrimaryKey


class AgentPresence(Base):
    """Whether a dashboard user is taking live chats. Online means available
    and a heartbeat within the last 75 seconds."""

    __tablename__ = "agent_presence"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class BotAnswer(UUIDPrimaryKey, TimestampCreated, Base):
    """An answer a person wrote for a question the bot couldn't answer."""

    __tablename__ = "bot_answers"

    bot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    # answer = a Q and A written for a question; summary = a reviewed, anonymised
    # note distilled from a conversation (`question` holds its title).
    kind: Mapped[str] = mapped_column(String(16), nullable=False, server_default="answer")
    # Where a shared note was first written, and the id every copy of it shares.
    origin_bot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bots.id", ondelete="SET NULL"), nullable=True
    )
    share_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
