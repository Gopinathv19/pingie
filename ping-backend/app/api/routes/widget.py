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
    IdentifyRequest,
    LiveUpdates,
    SendMessage,
    StartConversation,
    WidgetConfig,
)
from app.services import chat_service, live_service

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
