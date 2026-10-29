"""Allowed domains: where a bot's widget may load, and the install check."""

import re
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.db.models import AllowedDomain, Bot

HOST_RE = re.compile(r"^(\*\.)?([a-z0-9-]+\.)+[a-z]{2,}$")
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1"}
# Don't write last_seen_at on every widget load.
_TOUCH_INTERVAL = timedelta(minutes=1)


def normalize_host(value: str) -> str:
    host = value.strip().lower()
    host = re.sub(r"^https?://", "", host).split("/")[0].split(":")[0]
    if not HOST_RE.match(host):
        raise ValidationError("Enter a hostname like help.acme.com or *.acme.com")
    return host


def list_domains(db: Session, bot: Bot) -> list[AllowedDomain]:
    return list(db.scalars(select(AllowedDomain).where(AllowedDomain.bot_id == bot.id).order_by(AllowedDomain.created_at)))


def add_domain(db: Session, bot: Bot, host: str) -> AllowedDomain:
    host = normalize_host(host)
    if db.scalar(select(AllowedDomain).where(AllowedDomain.bot_id == bot.id, AllowedDomain.host == host)):
        raise ConflictError("That domain is already on the list")
    row = AllowedDomain(bot_id=bot.id, host=host)
    db.add(row)
    db.commit()
    return row


def remove_domain(db: Session, bot: Bot, domain_id: uuid.UUID) -> None:
    row = db.get(AllowedDomain, domain_id)
    if row is None or row.bot_id != bot.id:
        raise NotFoundError("Domain not found")
    db.delete(row)
    db.commit()


def host_matches(pattern: str, host: str) -> bool:
    if pattern.startswith("*."):
        base = pattern[2:]
        return host == base or host.endswith("." + base)
    return host == pattern


def match_origin(db: Session, bot: Bot, origin: str | None) -> AllowedDomain | str | None:
    """The allowed-domain row an Origin header matches, "localhost" for a
    permitted local origin, or None. A missing Origin never matches: the
    widget always runs in a browser, which always sends one cross-origin."""
    if not origin:
        return None
    host = (urlparse(origin).hostname or "").lower()
    if not host:
        return None
    if host in _LOCAL_HOSTS:
        return "localhost" if bot.allow_localhost else None
    for row in list_domains(db, bot):
        if host_matches(row.host, host):
            return row
    return None


def touch(db: Session, bot: Bot, row: AllowedDomain | str) -> None:
    now = datetime.now(UTC)
    changed = False
    if isinstance(row, AllowedDomain) and (row.last_seen_at is None or now - row.last_seen_at > _TOUCH_INTERVAL):
        row.last_seen_at = now
        changed = True
    if bot.last_seen_at is None or now - bot.last_seen_at > _TOUCH_INTERVAL:
        bot.last_seen_at = now
        changed = True
    if changed:
        db.commit()


def to_read(row: AllowedDomain) -> dict:
    return {
        "id": row.id,
        "host": row.host,
        "receiving_traffic": row.last_seen_at is not None,
        "last_seen_at": row.last_seen_at,
        "created_at": row.created_at,
    }
