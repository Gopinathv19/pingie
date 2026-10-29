"""Live chat: a person takes over a conversation from the bot.

    bot ──visitor asks for a person──▶ waiting ──agent joins──▶ human
     ▲                                    │                       │
     └──── nobody joined in time ─────────┘      hand back / end ─┘

Everything goes through the database and both sides poll, so it works with
any number of API processes. `expire_waiting` runs lazily on reads.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, ValidationError
from app.db.models import (
    AgentPresence,
    Bot,
    BotShare,
    Conversation,
    Message,
    OrganizationMember,
    Users,
    Visitor,
)
from app.services import notify

ONLINE_WINDOW = timedelta(seconds=75)
LIVE_STATUSES = ("waiting", "human")

WAITING_TEXT = "Connecting you with a person from the team… this usually takes a minute or two."
NO_AGENT_TEXT = "Our team isn't online right now. Leave your email and we'll get back to you."
MISSED_TEXT = "Sorry, everyone's busy right now. Leave your email and we'll get back to you soon."


def _now() -> datetime:
    return datetime.now(UTC)


def _agent_ids_query(bot: Bot):
    """Users who can reply on this bot: workspace editors/owners and editor shares."""
    members = select(OrganizationMember.user_id).where(
        OrganizationMember.organization_id == bot.organization_id, OrganizationMember.role.in_(("owner", "editor"))
    )
    shares = select(BotShare.user_id).where(BotShare.bot_id == bot.id, BotShare.role == "editor")
    return members.union(shares)


def agents_online(db: Session, bot: Bot) -> bool:
    return bool(db.scalar(
        select(func.count()).select_from(AgentPresence).where(
            AgentPresence.user_id.in_(_agent_ids_query(bot)),
            AgentPresence.available.is_(True),
            AgentPresence.last_seen_at > _now() - ONLINE_WINDOW,
        )
    ))


def _system(db: Session, conv: Conversation, text: str) -> Message:
    msg = Message(conversation_id=conv.id, bot_id=conv.bot_id, role="system", content=text)
    db.add(msg)
    conv.last_message_at = _now()
    return msg


# --- Visitor side ---------------------------------------------------------------------

def request_handoff(db: Session, bot: Bot, conv: Conversation) -> str:
    if conv.status in LIVE_STATUSES:
        return conv.status
    if not agents_online(db, bot):
        _ask_for_email(db, conv, NO_AGENT_TEXT)
        db.commit()
        return "unavailable"
    conv.status = "waiting"
    conv.handoff_requested_at = _now()
    conv.unread = True
    _system(db, conv, WAITING_TEXT)
    db.commit()
    return "waiting"


def _ask_for_email(db: Session, conv: Conversation, text: str) -> None:
    visitor = db.get(Visitor, conv.visitor_id)
    msg = _system(db, conv, text)
    if not (visitor and visitor.email):
        conv.awaiting_email = True
        msg.trace = {"asks_for_email": True}


def expire_waiting(db: Session, bot: Bot, conv: Conversation) -> None:
    if conv.status != "waiting" or not conv.handoff_requested_at:
        return
    if _now() - conv.handoff_requested_at < timedelta(seconds=get_settings().handoff_wait_seconds):
        return
    conv.status = "bot"
    _ask_for_email(db, conv, MISSED_TEXT)
    db.commit()
    question = db.scalar(
        select(Message.content)
        .where(Message.conversation_id == conv.id, Message.role == "visitor")
        .order_by(Message.created_at.desc())
        .limit(1)
    ) or ""
    notify.send_email(
        bot.handoff_email,
        f"[{bot.name}] Missed live chat",
        f"A visitor asked to talk to a person and nobody joined within "
        f"{get_settings().handoff_wait_seconds // 60} minutes.\n\nLast message: {question}\n\n"
        f"They were asked to leave their email. Open the Conversations inbox to follow up.",
    )


def _agent_brief(db: Session, conv: Conversation) -> dict | None:
    if not conv.assigned_user_id:
        return None
    user = db.get(Users, conv.assigned_user_id)
    if user is None:
        return None
    return {"name": (user.name or user.email).split()[0], "avatar_url": user.avatar_url}


def message_to_read(m: Message, authors: dict[uuid.UUID, str] | None = None) -> dict:
    return {
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "outcome": m.outcome,
        "citations": m.citations or [],
        "feedback": m.feedback,
        "created_at": m.created_at,
        "author_name": (authors or {}).get(m.author_user_id) if m.author_user_id else None,
        "asks_for_email": bool((m.trace or {}).get("asks_for_email")) if m.role == "system" else False,
    }


def authors_for(db: Session, messages: list[Message]) -> dict[uuid.UUID, str]:
    ids = {m.author_user_id for m in messages if m.author_user_id}
    if not ids:
        return {}
    return {u.id: (u.name or u.email).split()[0] for u in db.scalars(select(Users).where(Users.id.in_(ids)))}


def updates(db: Session, bot: Bot, conv: Conversation, after: datetime | None, roles: tuple[str, ...] | None = None) -> dict:
    expire_waiting(db, bot, conv)
    q = select(Message).where(Message.conversation_id == conv.id)
    if after is not None:
        q = q.where(Message.created_at > after)
    if roles:
        q = q.where(Message.role.in_(roles))
    messages = list(db.scalars(q.order_by(Message.created_at).limit(200)))
    authors = authors_for(db, messages)
    return {
        "status": conv.status,
        "agent": _agent_brief(db, conv),
        "messages": [message_to_read(m, authors) for m in messages],
    }


# --- Agent side -----------------------------------------------------------------------

def take_over(db: Session, conv: Conversation, agent: Users) -> None:
    if conv.status == "human" and conv.assigned_user_id == agent.id:
        return
    conv.status = "human"
    conv.assigned_user_id = agent.id
    conv.agent_joined_at = _now()
    conv.awaiting_email = False
    _system(db, conv, f"{(agent.name or agent.email).split()[0]} from the team joined the chat")
    db.commit()


def reply(db: Session, conv: Conversation, agent: Users, text: str) -> Message:
    text = text.strip()
    if not text:
        raise ValidationError("Write a message first")
    take_over(db, conv, agent)
    msg = Message(conversation_id=conv.id, bot_id=conv.bot_id, role="agent", content=text, author_user_id=agent.id)
    db.add(msg)
    conv.message_count += 1
    conv.last_message_at = _now()
    db.commit()
    return msg


def hand_back(db: Session, conv: Conversation) -> None:
    if conv.status not in LIVE_STATUSES:
        raise ConflictError("The bot is already handling this chat")
    conv.status = "bot"
    conv.assigned_user_id = None
    _system(db, conv, "You're chatting with the assistant again")
    db.commit()


def close(db: Session, conv: Conversation) -> None:
    if conv.status == "closed":
        return
    conv.status = "closed"
    _system(db, conv, "This chat has ended. Send a message any time to start again.")
    db.commit()


# --- Presence and the agent's live list -----------------------------------------------------

def heartbeat(db: Session, user: Users, available: bool) -> None:
    row = db.get(AgentPresence, user.id)
    if row is None:
        row = AgentPresence(user_id=user.id)
        db.add(row)
    row.available = available
    row.last_seen_at = _now()
    db.commit()


def _editable_bot_ids(user: Users):
    members = (
        select(Bot.id)
        .join(OrganizationMember, OrganizationMember.organization_id == Bot.organization_id)
        .where(OrganizationMember.user_id == user.id, OrganizationMember.role.in_(("owner", "editor")))
    )
    shares = select(BotShare.bot_id).where(BotShare.user_id == user.id, BotShare.role == "editor")
    return members.union(shares)


def live_summary(db: Session, user: Users) -> dict:
    bot_ids = _editable_bot_ids(user)
    rows = db.execute(
        select(Conversation, Bot, Visitor)
        .join(Bot, Bot.id == Conversation.bot_id)
        .join(Visitor, Visitor.id == Conversation.visitor_id)
        .where(
            Conversation.bot_id.in_(bot_ids),
            or_(
                Conversation.status == "waiting",
                and_(Conversation.status == "human", Conversation.assigned_user_id == user.id),
            ),
        )
        .order_by(Conversation.handoff_requested_at.asc().nulls_last(), Conversation.last_message_at.desc())
        .limit(50)
    ).all()
    waiting, mine = [], []
    for conv, bot, visitor in rows:
        expire_waiting(db, bot, conv)
        if conv.status not in LIVE_STATUSES:
            continue
        item = {
            "conversation_id": conv.id,
            "bot_id": bot.public_id,
            "bot_name": bot.name,
            "visitor": visitor.name or visitor.email or f"Visitor #{visitor.number}",
            "status": conv.status,
            "waiting_since": conv.handoff_requested_at,
            "last_message_at": conv.last_message_at,
            "unread": conv.unread,
        }
        (waiting if conv.status == "waiting" else mine).append(item)
    presence = db.get(AgentPresence, user.id)
    return {"available": bool(presence and presence.available), "waiting": waiting, "mine": mine}
