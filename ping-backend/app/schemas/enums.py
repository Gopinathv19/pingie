"""Allowed values for the VARCHAR status columns, enforced at the edge."""

from typing import Literal

BotStatus = Literal["live", "paused", "draft"]
ModelTier = Literal["fast", "balanced", "best"]
Tone = Literal["friendly", "professional", "concise"]
ReplyLanguage = Literal["auto", "en", "hi", "ta"]
HandoffMode = Literal["instant", "offer", "bot_first"]
MemoryMode = Literal["manual", "review", "auto"]
AnswerStrictness = Literal["strict", "balanced", "helpful"]
AlertEvent = Literal["wants_person", "lead", "disliked"]
SourceStatus = Literal["queued", "indexing", "ready", "failed"]
SourceType = Literal["pdf", "docx", "text", "url", "sitemap", "page"]
Outcome = Literal["answered", "partial", "fallback"]
TimeRange = Literal["24h", "7d", "30d", "90d"]
ConversationFilter = Literal["all", "live", "unanswered", "down", "handoff", "review", "unhappy"]
