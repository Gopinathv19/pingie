"""Bots: creation, settings, appearance, and the Memora subject behind each."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clients.memora import MemoraClient
from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, PingError, PlanRestrictionError, QuotaExceededError
from app.core.security import new_public_id, new_public_key
from app.db.models import (
    AllowedDomain,
    Bot,
    BotSource,
    Conversation,
    Organization,
    OrganizationMember,
)
from app.reasoning.pipeline import BotProfile
from app.schemas.appearance import WidgetAppearance
from app.schemas.bot import BotCreate, BotUpdate
from app.services import plan_service

log = logging.getLogger(__name__)

_COLORS = ["#7C3AED", "#0EA5E9", "#D97706", "#059669", "#DB2777", "#2563EB"]

DEFAULT_INSTRUCTIONS = (
    "You are the support assistant for {name}. Answer only from the provided sources. "
    "If the answer isn't in the sources, say you don't know and offer to collect the visitor's email. "
    "Keep answers under 120 words. Use short paragraphs and numbered steps for procedures."
)


def initials(name: str) -> str:
    words = [w for w in name.split() if w[:1].isalnum()]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def get_public_bot(db: Session, public_id: str) -> Bot:
    bot = db.scalar(select(Bot).where(Bot.public_id == public_id))
    if bot is None:
        raise NotFoundError("Bot not found")
    return bot


def create_bot(db: Session, org: Organization, payload: BotCreate) -> Bot:
    from app.services.organization_service import bot_count

    if bot_count(db, org.id) >= org.bots_limit:
        settings = get_settings()
        raise QuotaExceededError(
            f"Your plan allows {org.bots_limit} bots. "
            f"Email {settings.support_email} to upgrade your plan."
        )

    tiers = plan_service.allowed_tiers(db, org)
    model_tier = "balanced" if "balanced" in tiers else tiers[0]
    name = payload.name.strip()
    appearance = WidgetAppearance(title=name).model_dump()
    for _ in range(5):
        bot = Bot(
            organization_id=org.id,
            public_id=new_public_id("bot_"),
            public_key=new_public_key(),
            name=name,
            color=_COLORS[bot_count(db, org.id) % len(_COLORS)],
            status="draft",
            domain=payload.domain,
            instructions=DEFAULT_INSTRUCTIONS.format(name=name),
            model_tier=model_tier,
            appearance=appearance,
        )
        db.add(bot)
        try:
            db.flush()
            break
        except IntegrityError:  # public id collision: 36^7, but cheap to retry
            db.rollback()
    else:
        raise ConflictError("Could not allocate a bot id, try again")

    db.add(AllowedDomain(bot_id=bot.id, host=payload.domain))
    db.commit()
    return bot


def update_bot(db: Session, bot: Bot, payload: BotUpdate) -> Bot:
    updates = payload.model_dump(exclude_unset=True)
    if "model_tier" in updates:
        org = db.get(Organization, bot.organization_id)
        allowed = plan_service.allowed_tiers(db, org)
        if updates["model_tier"] not in allowed:
            settings = get_settings()
            raise PlanRestrictionError(
                f"The '{updates['model_tier']}' model tier requires a higher plan. "
                f"Email {settings.support_email} to upgrade."
            )
    for field, value in updates.items():
        if field in ("name", "domain", "handoff_email", "instructions", "fallback_message", "offline_message"):
            value = (value or "").strip()
        setattr(bot, field, value)
    db.commit()
    return bot


def delete_bot(db: Session, bot: Bot, memora: MemoraClient) -> None:
    """Delete the bot and, best effort, its Memora subject (sources, chunks,
    embeddings). A Memora outage must not leave the user unable to delete."""
    if bot.memora_subject_id is not None:
        try:
            memora.delete_subject(bot.memora_subject_id)
        except PingError as exc:
            log.warning("could not delete memora subject %s: %s", bot.memora_subject_id, exc.message)
    db.delete(bot)
    db.commit()


def ensure_subject(db: Session, bot: Bot, memora: MemoraClient) -> uuid.UUID:
    """The bot's Memora subject, created on first use."""
    if bot.memora_subject_id is not None:
        return bot.memora_subject_id
    try:
        subject_id = memora.create_subject(bot.public_id)
    except ConflictError:
        # Created earlier but our commit was lost; adopt it.
        subject_id = memora.find_subject(bot.public_id)
        if subject_id is None:
            raise
    bot.memora_subject_id = subject_id
    db.commit()
    return subject_id


def set_appearance(db: Session, bot: Bot, appearance: WidgetAppearance) -> WidgetAppearance:
    bot.appearance = appearance.model_dump()
    db.commit()
    return appearance


def appearance_of(bot: Bot) -> WidgetAppearance:
    return WidgetAppearance.model_validate(bot.appearance or {})


def profile(bot: Bot) -> BotProfile:
    return BotProfile(
        name=bot.name,
        subject_id=bot.memora_subject_id,
        instructions=bot.instructions,
        tone=bot.tone,
        language=bot.reply_language,
        tier=bot.model_tier,
        min_similarity=bot.min_similarity,
        fallback_message=bot.fallback_message,
        collect_email=bot.collect_email,
    )


def counts(db: Session, bot: Bot) -> dict:
    conversations = db.scalar(select(func.count(Conversation.id)).where(Conversation.bot_id == bot.id)) or 0
    sources = db.scalar(
        select(func.count(BotSource.id)).where(BotSource.bot_id == bot.id, BotSource.parent_id.is_(None))
    ) or 0
    domains = db.scalar(select(func.count(AllowedDomain.id)).where(AllowedDomain.bot_id == bot.id)) or 0
    live = db.scalar(
        select(func.count(Conversation.id)).where(
            Conversation.bot_id == bot.id, Conversation.status.in_(("waiting", "human"))
        )
    ) or 0
    return {"conversations": conversations, "sources": sources, "domains": domains, "live": live}


def to_detail(db: Session, bot: Bot, role: str = "owner", via: str = "workspace") -> dict:
    org = db.get(Organization, bot.organization_id)
    return {
        "access_role": role,
        "access_via": via,
        "organization_name": org.name if org else "",
        "id": bot.public_id,
        "organization_id": bot.organization_id,
        "name": bot.name,
        "initials": initials(bot.name),
        "color": bot.color,
        "status": bot.status,
        "domain": bot.domain,
        "public_key": bot.public_key,
        "instructions": bot.instructions,
        "model_tier": bot.model_tier,
        "tone": bot.tone,
        "reply_language": bot.reply_language,
        "min_similarity": bot.min_similarity if bot.min_similarity is not None else get_settings().reasoning_min_similarity,
        "fallback_message": bot.fallback_message,
        "collect_email": bot.collect_email,
        "handoff_email": bot.handoff_email,
        "offline_message": bot.offline_message,
        "allow_localhost": bot.allow_localhost,
        "appearance": appearance_of(bot),
        "counts": counts(db, bot),
        "created_at": bot.created_at,
        "updated_at": bot.updated_at,
    }


def list_summaries(db: Session, org: Organization) -> list[dict]:
    bots = db.scalars(select(Bot).where(Bot.organization_id == org.id).order_by(Bot.created_at)).all()
    return summaries(db, list(bots))


def summaries(db: Session, bots: list[Bot]) -> list[dict]:
    """Bot cards with their 30-day numbers, in three grouped queries."""
    if not bots:
        return []
    ids = [b.id for b in bots]
    since = datetime.now(UTC) - timedelta(days=30)
    conv = {
        row.bot_id: (row.total, row.resolved)
        for row in db.execute(
            select(
                Conversation.bot_id,
                func.count(Conversation.id).label("total"),
                func.sum(case((Conversation.outcome != "fallback", 1), else_=0)).label("resolved"),
            )
            .where(Conversation.bot_id.in_(ids), Conversation.created_at >= since)
            .group_by(Conversation.bot_id)
        )
    }
    srcs = dict(
        db.execute(
            select(BotSource.bot_id, func.count(BotSource.id))
            .where(BotSource.bot_id.in_(ids), BotSource.parent_id.is_(None))
            .group_by(BotSource.bot_id)
        ).all()
    )
    out = []
    for b in bots:
        total, resolved = conv.get(b.id, (0, 0))
        out.append({
            "id": b.public_id,
            "name": b.name,
            "initials": initials(b.name),
            "color": b.color,
            "status": b.status,
            "domain": b.domain,
            "conversations_30d": total,
            "resolution_rate": round(100 * (resolved or 0) / total) if total else 0,
            "sources": srcs.get(b.id, 0),
            "updated_at": b.updated_at,
        })
    return out
