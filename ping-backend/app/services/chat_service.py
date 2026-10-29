"""Visitor conversations: the widget's side of Ping.

One visitor turn is:

    precheck   rate limit + monthly quota (fails as an HTTP error)
    begin      store the visitor message; handle the cases that need no
               reasoning (paused bot, an email answering our request for one);
               otherwise run the reasoning pipeline up to generation
    generate   the LLM provider writes the answer (streamed or not)
    complete   store the bot reply with its outcome, citations and trace;
               roll the outcome up to the conversation

Streaming and non-streaming share every step except how `generate` is consumed.
"""

import hashlib
import json
import logging
import re
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clients.memora import get_memora
from app.clients.llm import StreamMeta, get_llm
from app.core.cache import TTLCache, normalise
from app.core.config import get_settings
from app.core.errors import NotFoundError, PermissionError_, PingError
from app.core.ratelimit import limiter
from app.core.security import conversation_from_token, create_conversation_token
from app.db.database import SessionLocal
from app.db.models import AllowedDomain, Bot, BotSource, Conversation, Lead, Message, Organization, Visitor
from app.reasoning.output import AnswerFilter
from app.reasoning.pipeline import Citation, Prepared, Reasoner, Reply, Turn, wants_human
from app.services import answer_service, bot_service, domain_service, live_service, notify, organization_service, source_service

log = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Conversation outcome is the worst reply outcome so far.
_RANK = {"answered": 0, "partial": 1, "fallback": 2}
_ERROR_TEXT = "Sorry, I'm having trouble answering right now. Please try again in a moment."


def reasoner() -> Reasoner:
    return Reasoner(get_memora(), get_llm())


# --- bot + origin -------------------------------------------------------------

def resolve_widget_bot(db: Session, public_id: str, origin: str | None) -> tuple[Bot, AllowedDomain | str]:
    """The bot, if this Origin may use it. Unknown bots and disallowed origins
    get distinct errors so a developer can tell a typo from a missing domain."""
    bot = bot_service.get_public_bot(db, public_id)
    match = domain_service.match_origin(db, bot, origin)
    if match is None:
        raise PermissionError_("This website is not on the bot's allowed domains")
    if bot.status == "draft" and match != "localhost":
        raise PermissionError_("This bot is not live yet")
    domain_service.touch(db, bot, match)
    return bot, match


def is_online(bot: Bot, match: AllowedDomain | str) -> bool:
    return bot.status == "live" or (bot.status == "draft" and match == "localhost")


def widget_config(db: Session, bot: Bot, match: AllowedDomain | str) -> dict:
    appearance = bot_service.appearance_of(bot)
    org = db.get(Organization, bot.organization_id)
    if org is not None and not org.remove_branding:
        appearance = appearance.model_copy(update={"show_branding": True})
    return {
        "bot_id": bot.public_id,
        "name": bot.name,
        "status": bot.status,
        "online": is_online(bot, match),
        "agents_online": live_service.agents_online(db, bot),
        "appearance": appearance,
    }


# --- conversations ------------------------------------------------------------

def start_conversation(
    db: Session, bot: Bot, anon_id: str, page_url: str, location: str, user_agent: str
) -> tuple[Conversation, str]:
    visitor = db.scalar(select(Visitor).where(Visitor.bot_id == bot.id, Visitor.anon_id == anon_id))
    if visitor is None:
        number = (db.scalar(select(func.max(Visitor.number)).where(Visitor.bot_id == bot.id)) or 0) + 1
        visitor = Visitor(bot_id=bot.id, anon_id=anon_id, number=number, location=location)
        db.add(visitor)
        db.flush()
    visitor.last_seen_at = datetime.now(UTC)
    if location:
        visitor.location = location

    path = urlparse(page_url).path or "/" if page_url else "/"
    conversation = Conversation(
        bot_id=bot.id,
        visitor_id=visitor.id,
        page_url=page_url[:2048],
        page_path=path[:1024],
        location=location,
        user_agent=user_agent[:512],
    )
    db.add(conversation)
    db.commit()
    return conversation, create_conversation_token(conversation.id, bot.id)


def load_conversation(db: Session, bot: Bot, token: str | None, conversation_id: uuid.UUID) -> Conversation:
    """The conversation in the URL, if the token was issued for it."""
    if not token:
        raise PermissionError_("Missing conversation token")
    if conversation_from_token(token, bot.id) != conversation_id:
        raise NotFoundError("Conversation not found")
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.bot_id != bot.id:
        raise NotFoundError("Conversation not found")
    return conversation


def identify(db: Session, conversation: Conversation, email: str | None, name: str | None) -> None:
    visitor = db.get(Visitor, conversation.visitor_id)
    if email:
        visitor.email = email.lower()
    if name:
        visitor.name = name
    db.commit()


def set_feedback(db: Session, conversation: Conversation, message_id: uuid.UUID, value: str) -> None:
    message = db.get(Message, message_id)
    if message is None or message.conversation_id != conversation.id or message.role != "bot":
        raise NotFoundError("Message not found")
    message.feedback = value
    db.commit()


# --- a visitor turn -----------------------------------------------------------

@dataclass
class VisitorTurn:
    visitor_message: Message
    started: float
    early: Reply | None = None      # answered without reasoning
    prepared: Prepared | None = None
    answer_key: tuple | None = None  # set on a first question: where its answer is cached


def precheck(db: Session, bot: Bot, client_key: str) -> None:
    limiter.check(f"{bot.id}:{client_key}", get_settings().widget_rate_limit_per_minute)
    organization_service.assert_message_quota(db, bot.organization_id)


def _history(db: Session, conversation: Conversation, before: uuid.UUID) -> list[Turn]:
    limit = get_settings().reasoning_history_turns
    rows = list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id, Message.id != before)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
    )
    return [
        Turn(role="user" if m.role == "visitor" else "assistant", content=m.content)
        for m in reversed(rows)
        if m.role != "system"
    ]


def begin(db: Session, bot: Bot, conversation: Conversation, text: str) -> VisitorTurn:
    started = time.monotonic()
    text = text.strip()
    visitor_message = Message(conversation_id=conversation.id, bot_id=bot.id, role="visitor", content=text)
    db.add(visitor_message)
    conversation.message_count += 1
    conversation.last_message_at = datetime.now(UTC)
    db.commit()
    turn = VisitorTurn(visitor_message=visitor_message, started=started)

    if conversation.status in live_service.LIVE_STATUSES:
        # A person is on it (or about to be): store the message, no bot reply.
        conversation.unread = True
        db.commit()
        turn.early = Reply(text="", outcome="human")
        return turn
    if conversation.status == "closed":
        conversation.status = "bot"
        db.commit()

    if bot.status == "paused":
        turn.early = Reply(
            text=bot.offline_message or "We're offline right now. Please check back later.",
            outcome="offline",
        )
        return turn

    if conversation.awaiting_email:
        match = EMAIL_RE.search(text)
        conversation.awaiting_email = False
        if match:
            turn.early = _capture_lead(db, bot, conversation, match.group(0).lower())
            return turn
        db.commit()
    elif EMAIL_RE.fullmatch(text) and _last_bot_outcome(db, conversation, visitor_message.id) == "fallback":
        # A bare email right after "leave your email", even when we already knew
        # an address for this visitor and so weren't waiting for one.
        turn.early = _capture_lead(db, bot, conversation, text.lower())
        return turn

    # The first time a visitor asks for a person the bot answers as usual, so
    # anything the team taught it for this can reply. Asking again means they
    # really want one, and that starts the handover.
    history = _history(db, conversation, visitor_message.id)
    if wants_human(text) and any(h.role == "user" and wants_human(h.content) for h in history):
        if live_service.agents_online(db, bot):
            live_service.request_handoff(db, bot, conversation)
            turn.early = Reply(text="", outcome="human", trace={"route": "handoff"})
        else:
            visitor = db.get(Visitor, conversation.visitor_id)
            if visitor and visitor.email:
                # Already have their email: pass it on instead of asking again.
                asked = next((h.content for h in reversed(history) if h.role == "user" and not wants_human(h.content)), None)
                turn.early = _capture_lead(db, bot, conversation, visitor.email, asked)
                turn.early.text = (
                    f"Our team isn't online right now, so I've passed your request on. "
                    f"They'll get back to you at {visitor.email}."
                )
            else:
                turn.early = Reply(
                    text=live_service.NO_AGENT_TEXT,
                    outcome="fallback",
                    asks_for_email=True,
                    trace={"route": "handoff_unavailable"},
                )
        return turn

    profile = bot_service.profile(bot)
    profile.knowledge_version = knowledge_version(db, bot)
    if not history:
        # A chat's first question doesn't depend on anything said before, so the
        # same question to the same knowledge gets the same answer.
        turn.answer_key = (bot.id, normalise(text), profile.knowledge_version)
        cached = answer_cache().get(turn.answer_key)
        if cached is not None:
            turn.early = replace(cached, trace={**cached.trace, "route": "answer_cache"})
            return turn

    try:
        turn.prepared = reasoner().prepare(
            profile, history, text, names=lambda ids: source_service.names_by_memora_id(db, bot.id, ids)
        )
        taught = _taught_reply(db, bot, turn.prepared)
        if taught is not None:
            turn.early = taught
    except PingError as exc:
        log.warning("reasoning failed for conversation %s: %s", conversation.id, exc.message)
        turn.early = Reply(text=_ERROR_TEXT, outcome="fallback", trace={"route": "error", "error": exc.message})
    return turn


_answer_cache: TTLCache | None = None


def answer_cache() -> TTLCache:
    global _answer_cache
    if _answer_cache is None:
        s = get_settings()
        _answer_cache = TTLCache(s.answer_cache_entries, s.answer_cache_ttl_seconds)
    return _answer_cache


def knowledge_version(db: Session, bot: Bot) -> str:
    """Changes whenever what the bot knows or how it answers changes: a source
    added, removed, resynced or finished indexing, taught answers synced, a chat
    pushed to chat memory, or the
    bot's answer settings edited. Keys the retrieval and answer caches."""
    count, synced, chunks, ready = db.execute(
        select(
            func.count(BotSource.id),
            func.max(BotSource.last_synced_at),
            func.coalesce(func.sum(BotSource.chunk_count), 0),
            func.count(BotSource.id).filter(BotSource.status == "ready"),
        ).where(BotSource.bot_id == bot.id)
    ).one()
    remembered = db.scalar(select(func.max(Conversation.memory_synced_at)).where(Conversation.bot_id == bot.id))
    settings = (bot.instructions, bot.tone, bot.reply_language, bot.model_tier, bot.min_similarity, bot.fallback_message)
    raw = f"{count}|{synced.isoformat() if synced else ''}|{chunks}|{ready}|{remembered}|{settings}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _taught_reply(db: Session, bot: Bot, prepared: Prepared) -> Reply | None:
    """A taught answer, sent word for word without the model, when retrieval put
    "Team answers" first and one taught question matches the visitor's words.

    The model paraphrased or ignored taught answers (and the conversation
    history pulled it off course), so an answer the team wrote is sent as written."""
    if prepared.kind != "generate" or not prepared.evidence:
        return None
    top = max(prepared.evidence, key=lambda c: c.rerank_score if c.rerank_score is not None else -99)
    if not (top.source_filename or "").startswith(answer_service.SOURCE_NAME):
        return None
    row = answer_service.match_taught_answer(db, bot, prepared.question)
    if row is None:
        return None
    citation = Citation(
        source_id=top.source_id, source_name=answer_service.SOURCE_NAME, location=row.question[:120],
        chunk_id=top.chunk_id, score=top.similarity,
    )
    return Reply(
        text=row.answer, outcome="answered", citations=[citation],
        trace={**prepared.trace, "route": "taught_answer", "answer_id": str(row.id)},
    )


def _last_bot_outcome(db: Session, conversation: Conversation, before: uuid.UUID) -> str | None:
    return db.scalar(
        select(Message.outcome)
        .where(Message.conversation_id == conversation.id, Message.role == "bot", Message.id != before)
        .order_by(Message.created_at.desc())
        .limit(1)
    )


def _capture_lead(db: Session, bot: Bot, conversation: Conversation, email: str, question: str | None = None) -> Reply:
    """The visitor answered "leave your email" with one (or asked for a person
    while we already had it)."""
    # The question behind the most recent fallback reply.
    question = question or db.scalar(
        select(Message.content)
        .where(Message.conversation_id == conversation.id, Message.role == "visitor")
        .where(Message.id.in_(
            select(Message.reply_to_id).where(
                Message.conversation_id == conversation.id, Message.outcome == "fallback"
            )
        ))
        .order_by(Message.created_at.desc())
        .limit(1)
    ) or ""
    visitor = db.get(Visitor, conversation.visitor_id)
    visitor.email = email
    conversation.handoff_email = email
    db.add(Lead(bot_id=bot.id, conversation_id=conversation.id, visitor_id=visitor.id, email=email, question=question))
    db.commit()
    notify.send_handoff(bot.handoff_email, bot.name, email, question)
    return Reply(
        text=f"Thanks! I've passed your question to the {bot.name} team. They'll get back to you at {email}.",
        outcome="lead",
    )


def complete(db: Session, bot: Bot, conversation: Conversation, turn: VisitorTurn, reply: Reply) -> Message:
    names = source_service.names_by_memora_id(db, bot.id, [c.source_id for c in reply.citations])
    citations = []
    for c in reply.citations:
        item = c.as_dict()
        item["source_name"] = names.get(c.source_id, c.source_name)
        citations.append(item)

    message = Message(
        conversation_id=conversation.id,
        bot_id=bot.id,
        reply_to_id=turn.visitor_message.id,
        role="bot",
        content=reply.text,
        outcome=reply.outcome,
        citations=citations,
        trace=reply.trace,
        latency_ms=int((time.monotonic() - turn.started) * 1000),
        first_token_ms=reply.first_token_ms,
        prompt_tokens=reply.prompt_tokens,
        completion_tokens=reply.completion_tokens,
        model=reply.model,
        gateway_query_id=reply.gateway_query_id,
    )
    db.add(message)
    conversation.message_count += 1
    conversation.last_message_at = datetime.now(UTC)
    conversation.unread = True
    if reply.outcome in _RANK and _RANK[reply.outcome] > _RANK.get(conversation.outcome, 0):
        conversation.outcome = reply.outcome
    if reply.asks_for_email:
        visitor = db.get(Visitor, conversation.visitor_id)
        conversation.awaiting_email = not (visitor and visitor.email)
    db.commit()
    return message


def _payload(db: Session, bot: Bot, conversation: Conversation, message: Message | None, reply: Reply) -> dict:
    if message is None:  # a person is handling the chat
        return {
            "message_id": None, "text": "", "outcome": "human", "citations": [],
            "asks_for_email": False, "offer_human": False, "status": conversation.status,
        }
    offer_human = reply.outcome == "fallback" and live_service.agents_online(db, bot)
    if offer_human:
        # Let the visitor choose a person first; asking for an email comes after.
        conversation.awaiting_email = False
        db.commit()
    return {
        "message_id": str(message.id),
        "text": message.content,
        "outcome": message.outcome,
        "citations": message.citations,
        "asks_for_email": reply.asks_for_email and not offer_human,
        "offer_human": offer_human,
        "status": conversation.status,
    }


def _finish(db: Session, bot: Bot, conversation: Conversation, turn: "VisitorTurn", reply: Reply) -> dict:
    if turn.answer_key is not None and reply.outcome == "answered" and reply.trace.get("route") in ("generate", "taught_answer"):
        answer_cache().set(turn.answer_key, replace(reply, first_token_ms=None))
    message = None if reply.outcome == "human" else complete(db, bot, conversation, turn, reply)
    return _payload(db, bot, conversation, message, reply)


def reply_once(db: Session, bot: Bot, conversation: Conversation, text: str) -> dict:
    turn = begin(db, bot, conversation, text)
    if turn.early is not None:
        reply = turn.early
    else:
        try:
            reply = reasoner().generate(bot_service.profile(bot), turn.prepared)
        except PingError as exc:
            reply = Reply(text=_ERROR_TEXT, outcome="fallback", trace={**turn.prepared.trace, "route": "error", "error": exc.message})
    return _finish(db, bot, conversation, turn, reply)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def reply_stream(bot_id: uuid.UUID, conversation_id: uuid.UUID, text: str) -> Iterator[str]:
    """Server-sent events: `delta` events with visitor-safe text, then one
    `done` event with the stored message. Runs on its own session because the
    request's session is closed before a streaming body is sent."""
    # Something on screen at once: retrieval and the model take a few seconds.
    yield _sse("status", {"text": "Searching the docs…"})
    with SessionLocal() as db:
        bot = db.get(Bot, bot_id)
        conversation = db.get(Conversation, conversation_id)
        turn = begin(db, bot, conversation, text)
        profile = bot_service.profile(bot)

        if turn.early is not None:
            reply = turn.early
            if reply.text:
                yield _sse("delta", {"text": reply.text})
        elif turn.prepared.kind != "generate":
            reply = reasoner().finish(profile, turn.prepared, None)
            yield _sse("delta", {"text": reply.text})
        else:
            meta = StreamMeta()
            f = AnswerFilter()
            try:
                for safe in reasoner().stream(profile, turn.prepared, meta, f):
                    yield _sse("delta", {"text": safe})
                reply = reasoner().finish(profile, turn.prepared, f.finish())
                if reply.outcome == "fallback":
                    # The model declined after we held its first words back;
                    # nothing was shown yet, so show the fallback.
                    yield _sse("delta", {"text": reply.text})
                reply.model = meta.model
                reply.gateway_query_id = meta.query_id
                reply.first_token_ms = meta.first_token_ms
                reply.prompt_tokens += meta.prompt_tokens
                reply.completion_tokens += meta.completion_tokens
            except PingError as exc:
                reply = Reply(text=_ERROR_TEXT, outcome="fallback", trace={**turn.prepared.trace, "route": "error", "error": exc.message})
                yield _sse("delta", {"text": ("\n\n" if f.has_output else "") + _ERROR_TEXT})

        yield _sse("done", _finish(db, bot, conversation, turn, reply))
