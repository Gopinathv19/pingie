"""Chat memory: finished chats a team member answered, pushed to Memora.

Each such chat becomes its own Memora source in the bot's subject, next to
its documents, so retrieval can surface how the team handled a similar
question before. Only the team's replies (with the customer message each
answered) are kept, scrubbed of emails and phone numbers; the bot's own
replies are left out (see prompts.scrubbed_transcript). These sources are not
Ping knowledge sources: they don't count against the plan's source quota and
are not listed on the Sources page.

A chat is finished once it is closed, or idle for `chat_memory_idle_minutes`
with nobody live on it. A message after the push re-pushes the chat and
drops the old copy. The status sweeper calls `archive_due`.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.clients.memora import MemoraClient
from app.core.config import get_settings
from app.core.errors import PingError
from app.db.models import Bot, Conversation, Message
from app.reasoning import prompts
from app.services import bot_service
from app.services.live_service import LIVE_STATUSES

log = logging.getLogger(__name__)

# Ping's name for these sources in prompts and citations.
SOURCE_NAME = prompts.PAST_CONVERSATIONS
_BATCH = 20
_MESSAGE_LIMIT = 200


def _due_query(now: datetime):
    cutoff = now - timedelta(minutes=get_settings().chat_memory_idle_minutes)
    team_replied = exists().where(Message.conversation_id == Conversation.id, Message.role == "agent")
    return (
        select(Conversation)
        .where(
            team_replied,
            Conversation.status.not_in(LIVE_STATUSES),
            or_(Conversation.status == "closed", Conversation.last_message_at < cutoff),
            or_(Conversation.memory_synced_at.is_(None), Conversation.last_message_at > Conversation.memory_synced_at),
        )
        .order_by(Conversation.last_message_at)
        .limit(_BATCH)
    )


def document(messages: list[Message]) -> str:
    note = prompts.scrubbed_transcript(messages)
    return f"# Conversation: {note['question']}\n\n{note['answer']}\n"


def archive(db: Session, memora: MemoraClient, conv: Conversation) -> None:
    """Push one chat (again) and commit; the previous copy is deleted after."""
    bot = db.get(Bot, conv.bot_id)
    if bot is None:
        return
    synced_through = conv.last_message_at
    messages = list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conv.id, Message.role.in_(("visitor", "bot", "agent")))
            .order_by(Message.created_at)
            .limit(_MESSAGE_LIMIT)
        )
    )
    subject_id = bot_service.ensure_subject(db, bot, memora)
    new_id = memora.push_text(subject_id, f"{SOURCE_NAME} {str(conv.id)[:8]}", document(messages))
    old_id = conv.memora_source_id
    conv.memora_source_id = new_id
    # The last message this copy includes: anything newer makes it due again.
    conv.memory_synced_at = synced_through
    try:
        db.commit()
    except Exception:
        db.rollback()
        _forget(memora, new_id)
        raise
    if old_id:
        _forget(memora, old_id)


def archive_due(db: Session, memora: MemoraClient) -> int:
    """Push chats that finished since the last sweep. Failures are retried
    on the next sweep."""
    if not get_settings().chat_memory_enabled:
        return 0
    done = 0
    for conv in list(db.scalars(_due_query(datetime.now(UTC)))):
        try:
            archive(db, memora, conv)
            done += 1
        except PingError as exc:
            log.warning("chat memory: could not push conversation %s: %s", conv.id, exc.message)
    return done


def forget_bot(db: Session, memora: MemoraClient, bot_id: uuid.UUID) -> None:
    """Delete every pushed chat of a bot from Memora (history cleared)."""
    ids = db.scalars(
        select(Conversation.memora_source_id).where(
            Conversation.bot_id == bot_id, Conversation.memora_source_id.is_not(None)
        )
    ).all()
    for source_id in ids:
        _forget(memora, source_id)


def names_by_memora_id(db: Session, bot_id: uuid.UUID, ids: list[uuid.UUID]) -> dict[str, str]:
    rows = db.scalars(
        select(Conversation.memora_source_id).where(
            Conversation.bot_id == bot_id, Conversation.memora_source_id.in_(ids)
        )
    ).all()
    return {str(mid): SOURCE_NAME for mid in rows}


def _forget(memora: MemoraClient, source_id: uuid.UUID) -> None:
    try:
        memora.delete_source(source_id)
    except PingError as exc:
        log.warning("chat memory: could not delete Memora source %s: %s", source_id, exc.message)
