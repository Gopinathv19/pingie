import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.enums import Outcome


class CitationRead(BaseModel):
    source_id: str | None = None
    source_name: str
    location: str = ""
    chunk_id: str | None = None
    score: float | None = None


class MessageRead(BaseModel):
    id: uuid.UUID
    role: Literal["visitor", "bot", "agent", "system"]
    content: str
    outcome: str | None
    citations: list[CitationRead]
    feedback: Literal["up", "down"] | None
    created_at: datetime
    author_name: str | None = None


class ConversationSummary(BaseModel):
    id: uuid.UUID
    visitor: str
    location: str
    page: str
    started_at: datetime
    last_message_at: datetime
    outcome: Outcome
    message_count: int
    preview: str
    unread: bool
    handoff_email: str | None
    status: Literal["bot", "waiting", "human", "closed"]
    assigned_to: str | None
    waiting_since: datetime | None


class ConversationPage(BaseModel):
    items: list[ConversationSummary]
    next_before: datetime | None


class ConversationDetail(ConversationSummary):
    duration_seconds: int
    messages: list[MessageRead]


class LeadRead(BaseModel):
    id: uuid.UUID
    email: str
    question: str
    conversation_id: uuid.UUID
    created_at: datetime


class AgentReply(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class ConversationUpdates(BaseModel):
    status: str
    agent: dict | None
    messages: list[MessageRead]
