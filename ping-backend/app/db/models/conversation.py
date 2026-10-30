import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.db.models.mixins import TimestampCreated, UUIDPrimaryKey


class Visitor(UUIDPrimaryKey, TimestampCreated, Base):
    """An anonymous website visitor, keyed by the id the widget keeps in
    localStorage. Email/name arrive from lead capture or Pingie.identify()."""

    __tablename__ = "visitors"
    __table_args__ = (UniqueConstraint("bot_id", "anon_id", name="uq_visitors_bot_anon"),)

    bot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    anon_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # Per-bot sequence for the "Visitor #4821" label.
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str] = mapped_column(String(120), nullable=False, server_default="")
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Conversation(UUIDPrimaryKey, TimestampCreated, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_bot_last", "bot_id", "last_message_at"),
        Index("ix_conversations_bot_status", "bot_id", "status"),
    )

    bot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bots.id", ondelete="CASCADE"), nullable=False
    )
    visitor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("visitors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_url: Mapped[str] = mapped_column(String(2048), nullable=False, server_default="")
    page_path: Mapped[str] = mapped_column(String(1024), nullable=False, server_default="/")
    location: Mapped[str] = mapped_column(String(120), nullable=False, server_default="")
    user_agent: Mapped[str] = mapped_column(String(512), nullable=False, server_default="")
    # Worst outcome of any bot reply: answered < partial < fallback.
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, server_default="answered")
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    unread: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    # The last bot reply asked for an email; the next visitor message is
    # checked for one before anything else.
    awaiting_email: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    handoff_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    # Who is answering: bot | waiting (visitor asked for a person) | human | closed.
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="bot")
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    handoff_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    agent_joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Chat memory (app/services/memory_service.py): the Memora source holding
    # this finished chat, and when it was pushed. A later message re-pushes it.
    memora_source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    memory_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # None (not considered yet) | pending (waiting for review) | learned (pushed)
    # | skipped (declined, failed the quality check, or forgotten: never re-pushed).
    memory_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # The visitor's rating of the whole chat: 1 unhappy, 2 neutral, 3 happy.
    # source: end (visitor ended it) | closed (an agent ended it) | inline.
    csat: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    csat_comment: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    csat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    csat_source: Mapped[str | None] = mapped_column(String(16), nullable=True)


class Message(UUIDPrimaryKey, TimestampCreated, Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
        Index("ix_messages_bot_created", "bot_id", "created_at"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    # Denormalised from the conversation: every analytics query filters by
    # bot and time, and this keeps them off a join.
    bot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bots.id", ondelete="CASCADE"), nullable=False
    )
    # The visitor message a bot reply answers. Pairs questions with outcomes.
    reply_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # visitor | bot | agent | system
    # The dashboard user who wrote an agent message.
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Bot replies only: answered | partial | fallback | smalltalk | lead
    outcome: Mapped[str | None] = mapped_column(String(16), nullable=True)
    citations: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    feedback: Mapped[str | None] = mapped_column(String(8), nullable=True)  # up | down
    # Reasoning trace: standalone query, retrieval scores, chunks kept.
    trace: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_token_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # VizhiOps query id, to open the call in the gateway's dashboard (empty for direct providers).
    gateway_query_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Lead(UUIDPrimaryKey, TimestampCreated, Base):
    """An email captured when the bot could not answer."""

    __tablename__ = "leads"

    bot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    visitor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("visitors.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
