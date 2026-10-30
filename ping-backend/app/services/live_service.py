"""Live chat: a person takes over a conversation from the bot.

    bot ──visitor asks for a person──▶ waiting ──agent joins──▶ human
     ▲                                    │                       │
     └──── nobody joined in time ─────────┘      hand back / end ─┘

Everything goes through the database and both sides poll, so it works with
any number of API processes. `expire_waiting` runs lazily on reads.
"""

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

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
from app.services import alert_service, notify

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


# --- Business hours ---------------------------------------------------------------

_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _hours(bot: Bot) -> dict | None:
    hours = bot.business_hours or {}
    return hours if hours.get("enabled") else None


def in_business_hours(bot: Bot, now: datetime | None = None) -> bool:
    """True when the bot has no hours set, or `now` falls in one of today's ranges."""
    hours = _hours(bot)
    if hours is None:
        return True
    local = (now or _now()).astimezone(ZoneInfo(hours.get("timezone") or "UTC"))
    hhmm = local.strftime("%H:%M")
    return any(start <= hhmm < end for start, end in hours.get("days", {}).get(_WEEKDAYS[local.weekday()], []))


def next_opening(bot: Bot, now: datetime | None = None) -> str | None:
    """When the team is next in, in the bot's time zone: "Monday 9:00 AM",
    "today 2:00 PM". None if no hours are set or no day is open."""
    hours = _hours(bot)
    if hours is None:
        return None
    local = (now or _now()).astimezone(ZoneInfo(hours.get("timezone") or "UTC"))
    days = hours.get("days", {})
    for ahead in range(8):
        day = local + timedelta(days=ahead)
        for start, _end in sorted(days.get(_WEEKDAYS[day.weekday()], [])):
            if ahead == 0 and start <= local.strftime("%H:%M"):
                continue
            h, m = (int(x) for x in start.split(":"))
            clock = f"{(h % 12) or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
            label = "today" if ahead == 0 else "tomorrow" if ahead == 1 else _DAY_NAMES[day.weekday()]
            return f"{label} {clock}"
    return None


def team_available(db: Session, bot: Bot) -> bool:
    """Someone can take a chat now: inside business hours and someone has Live on."""
    return in_business_hours(bot) and agents_online(db, bot)


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

# Asked for a person while nobody was online (or nobody joined in time). The
# chat stays with the bot but is flagged in the dashboard until someone joins.
REQUEST_WINDOW = timedelta(days=7)
# How long "I've already let the team know" stands in for a fresh notification.
# Past it, asking again notifies the team again rather than repeating the line.
RENOTIFY_WINDOW = timedelta(minutes=30)


def notified_recently(conv: Conversation) -> bool:
    return conv.handoff_requested_at is not None and _now() - conv.handoff_requested_at < RENOTIFY_WINDOW


def wants_person(conv: Conversation) -> bool:
    if conv.status != "bot" or conv.handoff_requested_at is None:
        return False
    if conv.agent_joined_at is not None and conv.agent_joined_at >= conv.handoff_requested_at:
        return False
    return _now() - conv.handoff_requested_at < REQUEST_WINDOW


def wants_person_clause():
    """`wants_person` as SQL, for lists and counts."""
    return and_(
        Conversation.status == "bot",
        Conversation.handoff_requested_at.is_not(None),
        Conversation.handoff_requested_at > _now() - REQUEST_WINDOW,
        or_(Conversation.agent_joined_at.is_(None), Conversation.agent_joined_at < Conversation.handoff_requested_at),
    )


def away_text(bot: Bot) -> str:
    """"Our team isn't online right now", or, outside business hours, when they're back."""
    if not in_business_hours(bot):
        back = next_opening(bot)
        return f"Our team is away right now{f' and back {back}' if back else ''}"
    return "Our team isn't online right now"


def offline_request_text(email: str | None, bot: Bot | None = None) -> str:
    away = away_text(bot) if bot is not None else "Our team isn't online right now"
    if email:
        return f"{away}, but I've let them know you'd like to talk to a person. They'll reply here, or at {email}."
    return f"{away}, but I've let them know you'd like to talk to a person. Leave your email so they can reach you."


def record_offline_request(db: Session, bot: Bot, conv: Conversation, announce: bool = True) -> tuple[str, bool]:
    """Flag the chat for the team and tell them by email. Returns the text for
    the visitor and whether it asks for their email."""
    visitor = db.get(Visitor, conv.visitor_id)
    email = visitor.email if visitor else None
    conv.handoff_requested_at = _now()
    conv.unread = True
    text = offline_request_text(email, bot)
    if announce:
        msg = _system(db, conv, text)
        if not email:
            conv.awaiting_email = True
            msg.trace = {"asks_for_email": True}
    elif not email:
        conv.awaiting_email = True
    db.commit()
    last = _last_visitor_text(db, conv)
    if email:
        notify.send_handoff(bot.handoff_email, bot.name, email, last)
    alert_service.fire(
        bot, "wants_person", visitor=alert_service.visitor_label(visitor), conversation_id=conv.id,
        email=email, text=f"{last} (team offline: flagged)" if last else "(team offline: flagged)",
    )
    return text, not email


def _last_visitor_text(db: Session, conv: Conversation) -> str:
    return db.scalar(
        select(Message.content)
        .where(Message.conversation_id == conv.id, Message.role == "visitor")
        .order_by(Message.created_at.desc())
        .limit(1)
    ) or ""


def request_handoff(db: Session, bot: Bot, conv: Conversation) -> str:
    if conv.status in LIVE_STATUSES:
        return conv.status
    if not team_available(db, bot):
        record_offline_request(db, bot, conv)
        return "unavailable"
    conv.status = "waiting"
    conv.handoff_requested_at = _now()
    conv.unread = True
    _system(db, conv, WAITING_TEXT)
    db.commit()
    visitor = db.get(Visitor, conv.visitor_id)
    alert_service.fire(
        bot, "wants_person", visitor=alert_service.visitor_label(visitor), conversation_id=conv.id,
        email=visitor.email if visitor else None, text=_last_visitor_text(db, conv),
    )
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
        "rated": conv.csat is not None,
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
                wants_person_clause(),
                and_(Conversation.status == "human", Conversation.assigned_user_id == user.id),
            ),
        )
        .order_by(Conversation.handoff_requested_at.asc().nulls_last(), Conversation.last_message_at.desc())
        .limit(50)
    ).all()
    waiting, mine = [], []
    for conv, bot, visitor in rows:
        expire_waiting(db, bot, conv)
        requested = wants_person(conv)
        if conv.status not in LIVE_STATUSES and not requested:
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
            "wants_person": requested,
        }
        (waiting if conv.status == "waiting" or requested else mine).append(item)
    presence = db.get(AgentPresence, user.id)
    return {"available": bool(presence and presence.available), "waiting": waiting, "mine": mine}
