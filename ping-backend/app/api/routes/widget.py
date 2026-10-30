"""The public API the embedded widget calls from customers' websites.

No dashboard session here. A request is allowed when its Origin is on the
bot's allowed domains; inside a conversation, the `X-Conversation-Token`
issued at start proves the visitor owns it.
"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Header, Request, status
from fastapi.responses import StreamingResponse

from app.api.deps import DbSession, client_ip, visitor_location
from app.core.config import get_settings
from app.core.ratelimit import limiter
from app.schemas.widget import (
    BotReply,
    ConversationStarted,
    FeedbackRequest,
    HandoffResult,
    HelpArticle,
    HelpFeedback,
    HelpList,
    IdentifyRequest,
    LiveUpdates,
    RatingRequest,
    SendMessage,
    StartConversation,
    WidgetConfig,
)
from app.services import chat_service, help_service, live_service

router = APIRouter(prefix="/widget/{bot_id}", tags=["widget"])

Origin = Annotated[str | None, Header()]
ConversationToken = Annotated[str | None, Header(alias="X-Conversation-Token")]


@router.get("/config", response_model=WidgetConfig)
def config(bot_id: str, db: DbSession, origin: Origin = None):
    """Appearance and online state. Loading this marks the domain as seen,
    which is what the install check reports."""
    bot, match = chat_service.resolve_widget_bot(db, bot_id, origin)
    return chat_service.widget_config(db, bot, match)


@router.post("/conversations", response_model=ConversationStarted, status_code=status.HTTP_201_CREATED)
def start(bot_id: str, payload: StartConversation, request: Request, db: DbSession, origin: Origin = None):
    bot, _ = chat_service.resolve_widget_bot(db, bot_id, origin)
    conversation, token = chat_service.start_conversation(
        db, bot, payload.visitor_id, payload.page_url, visitor_location(request),
        request.headers.get("user-agent", ""),
    )
    return {"conversation_id": conversation.id, "token": token}


@router.post("/conversations/{conversation_id}/messages", response_model=BotReply)
def send(
    bot_id: str,
    conversation_id: uuid.UUID,
    payload: SendMessage,
    request: Request,
    db: DbSession,
    origin: Origin = None,
    token: ConversationToken = None,
):
    """Ask a question. With `stream: true` the reply arrives as server-sent
    events: `delta` events with text, then a `done` event with the message."""
    bot, _ = chat_service.resolve_widget_bot(db, bot_id, origin)
    conversation = chat_service.load_conversation(db, bot, token, conversation_id)
    chat_service.precheck(db, bot, client_ip(request))
    if payload.stream:
        return StreamingResponse(
            chat_service.reply_stream(bot.id, conversation.id, payload.text),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    return chat_service.reply_once(db, bot, conversation, payload.text)


@router.post("/conversations/{conversation_id}/messages/{message_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
def feedback(
    bot_id: str,
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    payload: FeedbackRequest,
    db: DbSession,
    origin: Origin = None,
    token: ConversationToken = None,
) -> None:
    bot, _ = chat_service.resolve_widget_bot(db, bot_id, origin)
    conversation = chat_service.load_conversation(db, bot, token, conversation_id)
    chat_service.set_feedback(db, conversation, message_id, payload.value)


@router.post("/conversations/{conversation_id}/identify", status_code=status.HTTP_204_NO_CONTENT)
def identify(
    bot_id: str,
    conversation_id: uuid.UUID,
    payload: IdentifyRequest,
    db: DbSession,
    origin: Origin = None,
    token: ConversationToken = None,
) -> None:
    """`Pingie.identify({email, name})`: attribute the chat to a known user."""
    bot, _ = chat_service.resolve_widget_bot(db, bot_id, origin)
    conversation = chat_service.load_conversation(db, bot, token, conversation_id)
    chat_service.identify(db, conversation, payload.email, payload.name)


@router.post("/conversations/{conversation_id}/handoff", response_model=HandoffResult)
def request_handoff(
    bot_id: str,
    conversation_id: uuid.UUID,
    request: Request,
    db: DbSession,
    origin: Origin = None,
    token: ConversationToken = None,
):
    """The visitor asked for a person. `waiting` when an agent is online,
    otherwise `unavailable` and the next message is checked for an email."""
    bot, _ = chat_service.resolve_widget_bot(db, bot_id, origin)
    conversation = chat_service.load_conversation(db, bot, token, conversation_id)
    chat_service.precheck(db, bot, client_ip(request))
    return {"status": live_service.request_handoff(db, bot, conversation)}


@router.get("/conversations/{conversation_id}/updates", response_model=LiveUpdates)
def updates(
    bot_id: str,
    conversation_id: uuid.UUID,
    request: Request,
    db: DbSession,
    after: datetime | None = None,
    origin: Origin = None,
    token: ConversationToken = None,
):
    """Polled while a person is handling the chat: agent and system messages
    newer than `after`, plus who is answering."""
    bot, _ = chat_service.resolve_widget_bot(db, bot_id, origin)
    conversation = chat_service.load_conversation(db, bot, token, conversation_id)
    limiter.check(f"poll:{bot.id}:{client_ip(request)}", get_settings().widget_poll_rate_limit_per_minute)
    return live_service.updates(db, bot, conversation, after, roles=("agent", "system"))


@router.post("/conversations/{conversation_id}/end", status_code=status.HTTP_204_NO_CONTENT)
def end(
    bot_id: str,
    conversation_id: uuid.UUID,
    db: DbSession,
    origin: Origin = None,
    token: ConversationToken = None,
) -> None:
    """The visitor clicked End. A new message later reopens the chat."""
    bot, _ = chat_service.resolve_widget_bot(db, bot_id, origin)
    conversation = chat_service.load_conversation(db, bot, token, conversation_id)
    live_service.close(db, conversation)


@router.post("/conversations/{conversation_id}/rating", status_code=status.HTTP_204_NO_CONTENT)
def rate(
    bot_id: str,
    conversation_id: uuid.UUID,
    payload: RatingRequest,
    db: DbSession,
    origin: Origin = None,
    token: ConversationToken = None,
) -> None:
    """"How was your chat?": 1 unhappy, 2 neutral, 3 happy."""
    bot, _ = chat_service.resolve_widget_bot(db, bot_id, origin)
    conversation = chat_service.load_conversation(db, bot, token, conversation_id)
    chat_service.rate_conversation(db, conversation, payload.score, payload.comment, payload.source)


def _help_limit(bot_key: str, request: Request) -> None:
    limiter.check(f"help:{bot_key}:{client_ip(request)}", get_settings().widget_poll_rate_limit_per_minute)


@router.get("/help", response_model=HelpList)
def help_articles(bot_id: str, request: Request, db: DbSession, q: str = "", origin: Origin = None):
    """The Help Center: web pages and team answers, searchable."""
    bot, _ = chat_service.resolve_widget_bot(db, bot_id, origin)
    _help_limit(bot.public_id, request)
    return {"items": help_service.list_articles(db, bot, q)}


@router.get("/help/{article_id}", response_model=HelpArticle)
def help_article(bot_id: str, article_id: str, request: Request, db: DbSession, origin: Origin = None):
    bot, _ = chat_service.resolve_widget_bot(db, bot_id, origin)
    _help_limit(bot.public_id, request)
    return help_service.get_article(db, bot, article_id)


@router.post("/help/{article_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
def help_feedback(
    bot_id: str, article_id: str, payload: HelpFeedback, request: Request, db: DbSession, origin: Origin = None
) -> None:
    """"Did this answer your question?" on an article."""
    bot, _ = chat_service.resolve_widget_bot(db, bot_id, origin)
    _help_limit(bot.public_id, request)
    help_service.rate_article(db, bot, article_id, payload.helpful)
