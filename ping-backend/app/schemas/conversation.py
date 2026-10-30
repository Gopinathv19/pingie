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
    # set when the source is readable in the widget's Help Center
    article_id: str | None = None


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
    # asked for a person while nobody was online; cleared when someone joins
    wants_person: bool = False
    # learning from this chat: pending | learned | skipped (None: not considered)
    memory_status: str | None = None
    # the visitor's rating of the chat: 1 unhappy, 2 neutral, 3 happy
    csat: int | None = None
    csat_comment: str = ""


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
