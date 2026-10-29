import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.appearance import WidgetAppearance
from app.schemas.enums import BotStatus, ModelTier, ReplyLanguage, Tone


def _host(v: str) -> str:
    v = v.strip().lower()
    for prefix in ("https://", "http://"):
        if v.startswith(prefix):
            v = v[len(prefix):]
    return v.split("/")[0]


class BotCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    domain: str = Field(min_length=3, max_length=255)
    # Optional: start crawling right away (the "Crawl my website" wizard step).
    sitemap_url: str | None = Field(default=None, max_length=2048)

    @field_validator("domain")
    @classmethod
    def _domain(cls, v: str) -> str:
        return _host(v)


class BotUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    status: BotStatus | None = None
    domain: str | None = Field(default=None, min_length=3, max_length=255)
    instructions: str | None = Field(default=None, max_length=4000)
    model_tier: ModelTier | None = None
    tone: Tone | None = None
    reply_language: ReplyLanguage | None = None
    min_similarity: float | None = Field(default=None, ge=0.0, le=1.0)
    fallback_message: str | None = Field(default=None, max_length=1000)
    collect_email: bool | None = None
    handoff_email: str | None = Field(default=None, max_length=320)
    offline_message: str | None = Field(default=None, max_length=1000)
    allow_localhost: bool | None = None

    @field_validator("domain")
    @classmethod
    def _domain(cls, v: str | None) -> str | None:
        return _host(v) if v is not None else v


class BotCounts(BaseModel):
    conversations: int
    sources: int
    domains: int
    live: int = 0


class BotSummary(BaseModel):
    """A card on the All bots page."""

    id: str  # public id, e.g. bot_7f3k2a9
    name: str
    initials: str
    color: str
    status: BotStatus
    domain: str
    conversations_30d: int
    resolution_rate: int
    sources: int
    updated_at: datetime


class BotDetail(BaseModel):
    id: str
    organization_id: uuid.UUID
    organization_name: str
    access_role: str  # owner | editor | viewer
    access_via: str  # workspace | share
    name: str
    initials: str
    color: str
    status: BotStatus
    domain: str
    public_key: str
    instructions: str
    model_tier: ModelTier
    tone: Tone
    reply_language: ReplyLanguage
    min_similarity: float
    fallback_message: str
    collect_email: bool
    handoff_email: str
    offline_message: str
    allow_localhost: bool
    appearance: WidgetAppearance
    counts: BotCounts
    created_at: datetime
    updated_at: datetime
