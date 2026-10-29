"""The dashboard's inbox: listing, reading, exporting and clearing chats."""

import csv
import io
import uuid
from collections.abc import Iterator
from datetime import datetime

from sqlalchemy import delete, exists, or_, select
from sqlalchemy.orm import Session

from app.clients.memora import MemoraClient
from app.core.errors import NotFoundError
from app.db.database import SessionLocal
from app.db.models import Bot, Conversation, Lead, Message, Users, Visitor
from app.services import live_service, memory_service

PAGE_SIZE = 50


def _visitor_label(visitor: Visitor) -> str:
    return visitor.name or visitor.email or f"Visitor #{visitor.number}"


def list_conversations(
    db: Session, bot: Bot, filter_: str = "all", q: str = "", before: datetime | None = None
) -> dict:
    query = (
        select(Conversation, Visitor)
        .join(Visitor, Visitor.id == Conversation.visitor_id)
        .where(Conversation.bot_id == bot.id)
    )
    if filter_ == "live":
        query = query.where(Conversation.status.in_(live_service.LIVE_STATUSES))
    elif filter_ == "unanswered":
        query = query.where(Conversation.outcome == "fallback")
    elif filter_ == "down":
        query = query.where(
            exists().where(Message.conversation_id == Conversation.id, Message.feedback == "down")
        )
    elif filter_ == "handoff":
        query = query.where(Conversation.handoff_email.is_not(None))
    q = q.strip()
    if q:
        like = f"%{q}%"
        query = query.where(
            or_(
                exists().where(Message.conversation_id == Conversation.id, Message.content.ilike(like)),
                Visitor.email.ilike(like),
                Visitor.name.ilike(like),
            )
        )
    if before is not None:
        query = query.where(Conversation.last_message_at < before)
    order = [Conversation.last_message_at.desc()]
    if filter_ == "live":
        order.insert(0, (Conversation.status != "waiting"))
    rows = db.execute(query.order_by(*order).limit(PAGE_SIZE + 1)).all()
    for c, _ in rows:
        live_service.expire_waiting(db, bot, c)
    has_more = len(rows) > PAGE_SIZE
    rows = rows[:PAGE_SIZE]

    previews = _first_questions(db, [c.id for c, _ in rows])
    agents = _agent_names(db, [c.assigned_user_id for c, _ in rows])
    items = [_summary(c, v, previews.get(c.id, ""), agents) for c, v in rows]
    return {"items": items, "next_before": rows[-1][0].last_message_at if has_more and rows else None}


def _first_questions(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    rows = db.execute(
        select(Message.conversation_id, Message.content)
        .where(Message.conversation_id.in_(ids), Message.role == "visitor")
        .distinct(Message.conversation_id)
        .order_by(Message.conversation_id, Message.created_at)
    ).all()
    return {cid: content for cid, content in rows}


def _user_names(db: Session, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    return _agent_names(db, list(ids))


def _agent_names(db: Session, ids: list[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    wanted = {i for i in ids if i}
    if not wanted:
        return {}
    return {u.id: (u.name or u.email).split()[0] for u in db.scalars(select(Users).where(Users.id.in_(wanted)))}


def _summary(c: Conversation, v: Visitor, preview: str, agents: dict[uuid.UUID, str] | None = None) -> dict:
    return {
        "id": c.id,
        "visitor": _visitor_label(v),
        "location": c.location or v.location,
        "page": c.page_path,
        "started_at": c.created_at,
        "last_message_at": c.last_message_at,
        "outcome": c.outcome,
        "message_count": c.message_count,
        "preview": preview[:200],
        "unread": c.unread,
        "handoff_email": c.handoff_email,
        "status": c.status,
        "assigned_to": (agents or {}).get(c.assigned_user_id) if c.assigned_user_id else None,
        "waiting_since": c.handoff_requested_at if c.status == "waiting" else None,
    }


def get_conversation(db: Session, bot: Bot, conversation_id: uuid.UUID, mark_read: bool = True) -> dict:
    row = db.execute(
        select(Conversation, Visitor)
        .join(Visitor, Visitor.id == Conversation.visitor_id)
        .where(Conversation.id == conversation_id)
    ).first()
    if row is None or row[0].bot_id != bot.id:
        raise NotFoundError("Conversation not found")
    c, v = row
    live_service.expire_waiting(db, bot, c)
    messages = list(
        db.scalars(select(Message).where(Message.conversation_id == c.id).order_by(Message.created_at))
    )
    if mark_read and c.unread:
        c.unread = False
        db.commit()
    # Agent and message authors in a single users query.
    authors = _user_names(db, {c.assigned_user_id, *(m.author_user_id for m in messages)})
    detail = _summary(c, v, messages[0].content if messages else "", authors)
    detail["duration_seconds"] = int((c.last_message_at - c.created_at).total_seconds())
    detail["messages"] = [live_service.message_to_read(m, authors) for m in messages]
    return detail


def export_csv(bot_id: uuid.UUID) -> Iterator[str]:
    """One row per message, streamed so a large history never sits in memory.

    Opens its own session: the request's session is closed before a
    streaming body is sent, and reusing it would leave a transaction open.
    """
    with SessionLocal() as db:
        yield from _export_rows(db, bot_id)


def _export_rows(db: Session, bot_id: uuid.UUID) -> Iterator[str]:
    buf = io.StringIO()
    writer = csv.writer(buf)

    def flush() -> str:
        value = buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        return value

    writer.writerow(["conversation_id", "started_at", "visitor", "page", "role", "message", "outcome", "feedback", "sources", "sent_at"])
    yield flush()
    rows = db.execute(
        select(Conversation, Visitor, Message)
        .join(Visitor, Visitor.id == Conversation.visitor_id)
        .join(Message, Message.conversation_id == Conversation.id)
        .where(Conversation.bot_id == bot_id)
        .order_by(Conversation.created_at.desc(), Message.created_at)
        .execution_options(yield_per=500)
    )
    for c, v, m in rows:
        writer.writerow([
            c.id, c.created_at.isoformat(), _visitor_label(v), c.page_path, m.role, m.content,
            m.outcome or "", m.feedback or "",
            "; ".join(cit.get("source_name", "") for cit in (m.citations or [])),
            m.created_at.isoformat(),
        ])
        yield flush()


def clear_history(db: Session, bot: Bot, memora: MemoraClient | None = None) -> int:
    """Delete every chat, and the copies chat memory pushed to Memora."""
    if memora is not None:
        memory_service.forget_bot(db, memora, bot.id)
    result = db.execute(delete(Conversation).where(Conversation.bot_id == bot.id))
    db.execute(delete(Visitor).where(Visitor.bot_id == bot.id))
    db.commit()
    return result.rowcount or 0


def list_leads(db: Session, bot: Bot) -> list[Lead]:
    return list(db.scalars(select(Lead).where(Lead.bot_id == bot.id).order_by(Lead.created_at.desc()).limit(500)))
