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

Each bot chooses how much of this happens (`Bot.memory_mode`):
    manual  nothing is learned on its own; only Save as knowledge
    review  finished chats wait as `pending` until a teammate approves one
    auto    finished chats are learned on their own, if `worth_learning`
A chat's state is `Conversation.memory_status`: pending | learned | skipped.
Skipped chats (declined, failed the check, or forgotten) are never pushed
again by the sweeper; a teammate can still approve one.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.clients.memora import MemoraClient
from app.core.config import get_settings
from app.core.errors import PingError, ValidationError
from app.db.models import Bot, Conversation, Message
from app.reasoning import prompts
from app.services import bot_service
from app.services.live_service import LIVE_STATUSES

log = logging.getLogger(__name__)

# Ping's name for these sources in prompts and citations.
SOURCE_NAME = prompts.PAST_CONVERSATIONS
_BATCH = 20
_MESSAGE_LIMIT = 200


# A teammate's replies shorter than this in total ("hi", "ok") teach nothing.
_MIN_TEAM_TEXT = 40


def _due_query(now: datetime):
    cutoff = now - timedelta(minutes=get_settings().chat_memory_idle_minutes)
    team_replied = exists().where(Message.conversation_id == Conversation.id, Message.role == "agent")
    return (
        select(Conversation)
        .join(Bot, Bot.id == Conversation.bot_id)
        .where(
            Bot.memory_mode.in_(("review", "auto")),
            team_replied,
            Conversation.status.not_in(LIVE_STATUSES),
            or_(Conversation.status == "closed", Conversation.last_message_at < cutoff),
            or_(Conversation.memory_status.is_(None), Conversation.memory_status != "skipped"),
            or_(Conversation.memory_synced_at.is_(None), Conversation.last_message_at > Conversation.memory_synced_at),
        )
        .order_by(Conversation.last_message_at)
        .limit(_BATCH)
    )


def _messages(db: Session, conv: Conversation) -> list[Message]:
    return list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conv.id, Message.role.in_(("visitor", "bot", "agent")))
            .order_by(Message.created_at)
            .limit(_MESSAGE_LIMIT)
        )
    )


def worth_learning(messages: list[Message]) -> bool:
    """Automatic mode's guard against teaching the bot noise: the team must
    have actually answered something, and nobody disliked what followed."""
    team = [m for m in messages if m.role == "agent"]
    if len(" ".join(prompts.scrub(m.content) for m in team).strip()) < _MIN_TEAM_TEXT:
        return False
    first_team = team[0].created_at
    return not any(m.feedback == "down" and m.created_at >= first_team for m in messages)


def document(messages: list[Message]) -> str:
    note = prompts.scrubbed_transcript(messages)
    return f"# Conversation: {note['question']}\n\n{note['answer']}\n"


def archive(db: Session, memora: MemoraClient, conv: Conversation) -> None:
    """Push one chat (again) and commit; the previous copy is deleted after."""
    bot = db.get(Bot, conv.bot_id)
    if bot is None:
        return
    synced_through = conv.last_message_at
    messages = _messages(db, conv)
    subject_id = bot_service.ensure_subject(db, bot, memora)
    new_id = memora.push_text(subject_id, f"{SOURCE_NAME} {str(conv.id)[:8]}", document(messages))
    old_id = conv.memora_source_id
    conv.memora_source_id = new_id
    conv.memory_status = "learned"
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
        bot = db.get(Bot, conv.bot_id)
        if bot is None:
            continue
        if bot.memory_mode == "review":
            # Queue it; a teammate decides. Newer messages bring a learned chat
            # back for review too. Marking it synced stops it re-queuing each sweep.
            conv.memory_status = "pending"
            conv.memory_synced_at = conv.last_message_at
            db.commit()
            done += 1
            continue
        if not worth_learning(_messages(db, conv)):
            _drop(db, memora, conv)
            continue
        try:
            archive(db, memora, conv)
            done += 1
        except PingError as exc:
            log.warning("chat memory: could not push conversation %s: %s", conv.id, exc.message)
    return done


def approve(db: Session, memora: MemoraClient, conv: Conversation) -> None:
    """A teammate says: learn from this chat (any mode)."""
    if not any(m.role == "agent" for m in _messages(db, conv)):
        raise ValidationError("Only chats a team member replied in can be learned")
    archive(db, memora, conv)


def skip(db: Session, memora: MemoraClient, conv: Conversation) -> None:
    """A teammate says: don't learn from this chat, or forget it if learned."""
    _drop(db, memora, conv)


def _drop(db: Session, memora: MemoraClient, conv: Conversation) -> None:
    old_id = conv.memora_source_id
    conv.memora_source_id = None
    conv.memory_status = "skipped"
    # Stays "synced", so the sweeper never picks it up again by itself.
    conv.memory_synced_at = conv.last_message_at
    db.commit()
    if old_id:
        _forget(memora, old_id)


def forget_learned(db: Session, memora: MemoraClient, bot: Bot) -> int:
    """Remove every chat this bot learned from Memora; they stay skipped."""
    rows = list(
        db.scalars(
            select(Conversation).where(
                Conversation.bot_id == bot.id,
                or_(Conversation.memory_status == "learned", Conversation.memora_source_id.is_not(None)),
            )
        )
    )
    for conv in rows:
        _drop(db, memora, conv)
    return len(rows)


def stats(db: Session, bot: Bot) -> dict:
    counts = dict(
        db.execute(
            select(Conversation.memory_status, func.count())
            .where(Conversation.bot_id == bot.id, Conversation.memory_status.in_(("learned", "pending")))
            .group_by(Conversation.memory_status)
        ).all()
    )
    return {"learned": counts.get("learned", 0), "pending": counts.get("pending", 0)}


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
