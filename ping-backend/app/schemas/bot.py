import re
import uuid
from datetime import datetime
from zoneinfo import available_timezones

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.appearance import WidgetAppearance
from app.schemas.enums import (
    AlertEvent, AnswerStrictness, BotStatus, HandoffMode, MemoryMode, ModelTier, ReplyLanguage, Tone,
)


def _host(v: str) -> str:
    v = v.strip().lower()
    for prefix in ("https://", "http://"):
        if v.startswith(prefix):
            v = v[len(prefix):]
    return v.split("/")[0]


WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class BusinessHours(BaseModel):
    """When the team takes chats. Outside these hours a handover is flagged
    and emailed instead of connecting someone (live_service.in_business_hours)."""

    enabled: bool = False
    timezone: str = "UTC"
    # weekday -> up to 3 [start, end] ranges, "HH:MM" 24h; a missing day is closed
    days: dict[str, list[tuple[str, str]]] = Field(default_factory=dict)

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str) -> str:
        if v not in available_timezones():
            raise ValueError("Unknown time zone")
        return v

    @model_validator(mode="after")
    def _ranges(self) -> "BusinessHours":
        for day, ranges in self.days.items():
            if day not in WEEKDAYS:
                raise ValueError(f"Unknown weekday: {day}")
            if len(ranges) > 3:
                raise ValueError("At most 3 time ranges per day")
            for start, end in ranges:
                if not (_HHMM.match(start) and _HHMM.match(end)) or start >= end:
                    raise ValueError(f"{day}: use HH:MM, with the start before the end")
        return self


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
    handoff_mode: HandoffMode | None = None
    memory_mode: MemoryMode | None = None
    answer_strictness: AnswerStrictness | None = None
    topic_guard: bool | None = None
    blocked_topics: str | None = Field(default=None, max_length=2000)
    off_topic_message: str | None = Field(default=None, max_length=1000)
    business_hours: BusinessHours | None = None
    alert_slack_url: str | None = Field(default=None, max_length=512)
    alert_webhook_url: str | None = Field(default=None, max_length=512)
    alert_events: list[AlertEvent] | None = None
    allow_localhost: bool | None = None

    @field_validator("domain")
    @classmethod
    def _domain(cls, v: str | None) -> str | None:
        return _host(v) if v is not None else v

    @field_validator("alert_slack_url")
    @classmethod
    def _slack(cls, v: str | None) -> str | None:
        if v and not v.strip().startswith("https://hooks.slack.com/"):
            raise ValueError("Use a Slack incoming webhook URL (https://hooks.slack.com/...)")
        return v.strip() if v else v

    @field_validator("alert_webhook_url")
    @classmethod
    def _webhook(cls, v: str | None) -> str | None:
        if v and not v.strip().startswith("https://"):
            raise ValueError("The webhook URL must start with https://")
        return v.strip() if v else v

    @field_validator("alert_events")
    @classmethod
    def _events(cls, v: list[str] | None) -> list[str] | None:
        return sorted(set(v)) if v is not None else v


class MemoryStats(BaseModel):
    learned: int = 0
    pending: int = 0


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
    handoff_mode: HandoffMode
    # whether a teammate has Live on right now, so a handover can connect someone
    agents_online: bool = False
    memory_mode: MemoryMode
    memory: "MemoryStats"
    answer_strictness: AnswerStrictness = "balanced"
    topic_guard: bool = False
    blocked_topics: str = ""
    off_topic_message: str = ""
    business_hours: BusinessHours = Field(default_factory=BusinessHours)
    # outside business hours right now, and when the team is back
    outside_hours: bool = False
    next_opening: str | None = None
    # empty for viewers; `alerts_configured` says whether any URL is set
    alert_slack_url: str = ""
    alert_webhook_url: str = ""
    alerts_configured: bool = False
    alert_events: list[AlertEvent] = Field(default_factory=list)
    allow_localhost: bool
    appearance: WidgetAppearance
    counts: BotCounts
    created_at: datetime
    updated_at: datetime
