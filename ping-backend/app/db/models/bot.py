import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.db.models.mixins import TimestampCreated, TimestampUpdated, UUIDPrimaryKey


class Bot(UUIDPrimaryKey, TimestampCreated, TimestampUpdated, Base):
    """One support bot: its knowledge (a Memora subject), its answering
    behaviour, and the widget it renders on allowed domains."""

    __tablename__ = "bots"
    __table_args__ = (UniqueConstraint("public_id", name="uq_bots_public_id"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # `bot_7f3k2a9`: in URLs, the embed snippet and the Memora subject's
    # external_id. The UUID never leaves the backend.
    public_id: Mapped[str] = mapped_column(String(32), nullable=False)
    public_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    color: Mapped[str] = mapped_column(String(16), nullable=False, server_default="#7C3AED")
    # live | paused | draft
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="draft")
    # Primary website, e.g. help.acme.com. Allowed domains are separate rows.
    domain: Mapped[str] = mapped_column(String(255), nullable=False, server_default="")
    # Created lazily on the first source, so a Memora outage never blocks
    # creating a bot.
    memora_subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # --- Answering behaviour (Bot settings page) ---
    instructions: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    model_tier: Mapped[str] = mapped_column(String(16), nullable=False, server_default="balanced")
    tone: Mapped[str] = mapped_column(String(16), nullable=False, server_default="friendly")
    reply_language: Mapped[str] = mapped_column(String(16), nullable=False, server_default="auto")
    min_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    fallback_message: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    collect_email: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    handoff_email: Mapped[str] = mapped_column(String(320), nullable=False, server_default="")
    offline_message: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    # When a visitor asks for a person: "instant" hands over at once, "offer"
    # replies with a "Talk to a person" button, "bot_first" answers as usual
    # with the button under it. Asking again (or the button) always hands over.
    handoff_mode: Mapped[str] = mapped_column(String(16), nullable=False, server_default="offer")
    # How the bot learns from finished chats a teammate answered
    # (app/services/memory_service.py): "manual" only through Save as
    # knowledge, "review" after a teammate approves each chat, "auto" by itself.
    memory_mode: Mapped[str] = mapped_column(String(16), nullable=False, server_default="manual")
    # How cautious answers are: strict | balanced | helpful (pipeline rerank floor + one prompt rule).
    answer_strictness: Mapped[str] = mapped_column(String(16), nullable=False, server_default="balanced")
    # Decline questions that aren't about this bot's business (chat_service._off_topic).
    topic_guard: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    blocked_topics: Mapped[str] = mapped_column(Text, nullable=False, server_default="")  # one per line
    off_topic_message: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    # {"enabled", "timezone", "days": {"mon": [["09:00", "18:00"]], ...}}; {} = no hours set.
    business_hours: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    # Where to post alerts (app/services/alert_service.py), and for which events.
    alert_slack_url: Mapped[str] = mapped_column(String(512), nullable=False, server_default="")
    alert_webhook_url: Mapped[str] = mapped_column(String(512), nullable=False, server_default="")
    alert_events: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default='["wants_person", "lead", "disliked"]'
    )
    # The single "Team answers" source that holds answers taught from the inbox.
    # No FK: bot_sources already references bots, and a deleted row is detected.
    faq_source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # --- Widget ---
    appearance: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    allow_localhost: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
