import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.appearance import WidgetAppearance
from app.schemas.conversation import CitationRead


class WidgetConfig(BaseModel):
    bot_id: str
    name: str
    status: str
    online: bool
    agents_online: bool = False
    # the bot has articles visitors can browse
    help_center: bool = False
    appearance: WidgetAppearance


class StartConversation(BaseModel):
    # The id the widget keeps in localStorage; it identifies a returning visitor.
    visitor_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    page_url: str = Field(default="", max_length=2048)


class ConversationStarted(BaseModel):
    conversation_id: uuid.UUID
    token: str


class SendMessage(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    stream: bool = False


class BotReply(BaseModel):
    message_id: uuid.UUID | None
    text: str
    outcome: str
    citations: list[CitationRead]
    asks_for_email: bool
    offer_human: bool = False
    status: str = "bot"


class HandoffResult(BaseModel):
    status: str  # waiting | human | unavailable


class LiveMessage(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    outcome: str | None
    citations: list[CitationRead]
    created_at: datetime
    author_name: str | None
    asks_for_email: bool


class LiveAgent(BaseModel):
    name: str
    avatar_url: str


class LiveUpdates(BaseModel):
    status: str
    agent: LiveAgent | None
    messages: list[LiveMessage]
    # the visitor already rated this chat, so the widget doesn't ask again
    rated: bool = False


class RatingRequest(BaseModel):
    score: int = Field(ge=1, le=3)
    comment: str = Field(default="", max_length=500)
    source: str = Field(default="end", pattern=r"^(end|closed|inline)$")


class HelpArticleSummary(BaseModel):
    id: str  # "<kind>:<uuid>", kind = page | answer
    title: str
    snippet: str
    url: str | None = None


class HelpArticle(HelpArticleSummary):
    body: str  # markdown


class HelpList(BaseModel):
    items: list[HelpArticleSummary]


class HelpFeedback(BaseModel):
    helpful: bool


class FeedbackRequest(BaseModel):
    value: str = Field(pattern=r"^(up|down)$")


class IdentifyRequest(BaseModel):
    email: EmailStr | None = None
    name: str | None = Field(default=None, max_length=255)
