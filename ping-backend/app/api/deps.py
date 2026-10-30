"""Shared request dependencies.

Two kinds of caller:

* A **dashboard user**, carrying the `ping_session` cookie set by Google
  sign-in (or the same JWT as a Bearer token). Every bot route resolves the
  bot through the user's organization membership, so a bot id in the URL is
  never trusted on its own.
* A **website visitor**, through the public widget routes. They are
  authorised by the page's Origin (the bot's allowed domains) and, inside a
  conversation, by the conversation token issued when it started.
"""

from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.clients.memora import MemoraClient, get_memora
from app.clients.llm import LLMClient, get_llm
from app.core.config import get_settings
from app.core.errors import AuthenticationError
from app.core.security import session_user_id
from app.db.database import get_db
from app.db.models import Bot, Users
from app.reasoning.pipeline import Reasoner
from app.services import auth_service
from app.services.access_service import BotAccess, require_bot_role

DbSession = Annotated[Session, Depends(get_db)]


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def get_current_user(
    db: DbSession,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> Users:
    token = request.cookies.get(get_settings().auth_cookie_name) or _bearer(authorization)
    if not token:
        raise AuthenticationError("Not authenticated")
    user = auth_service.get_user(db, session_user_id(token))
    if user is None:
        raise AuthenticationError("User no longer exists")
    if user.status != "active":
        raise AuthenticationError("This account is disabled")
    return user


CurrentUser = Annotated[Users, Depends(get_current_user)]


def get_optional_user(
    db: DbSession,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> Users | None:
    try:
        return get_current_user(db, request, authorization)
    except AuthenticationError:
        return None


OptionalUser = Annotated[Users | None, Depends(get_optional_user)]


def _bot_access(min_role: str):
    """`{bot_id}` in a dashboard path, resolved through membership or a share."""

    def dep(bot_id: str, db: DbSession, user: CurrentUser) -> BotAccess:
        return require_bot_role(db, user, bot_id, min_role)

    return dep


def _bot(min_role: str):
    access = _bot_access(min_role)

    def dep(a: Annotated[BotAccess, Depends(access)]) -> Bot:
        return a.bot

    return dep


def get_reasoner() -> Reasoner:
    return Reasoner(get_memora(), get_llm())


ViewerAccess = Annotated[BotAccess, Depends(_bot_access("viewer"))]
EditorAccess = Annotated[BotAccess, Depends(_bot_access("editor"))]
CurrentBot = Annotated[Bot, Depends(_bot("viewer"))]
EditableBot = Annotated[Bot, Depends(_bot("editor"))]
OwnedBot = Annotated[Bot, Depends(_bot("owner"))]
Memora = Annotated[MemoraClient, Depends(get_memora)]
LLM = Annotated[LLMClient, Depends(get_llm)]
ReasonerDep = Annotated[Reasoner, Depends(get_reasoner)]


def client_ip(request: Request) -> str:
    """The visitor's IP, for rate limits. Behind `trusted_proxy_hops` proxies the
    entry they appended to X-Forwarded-For; the entries to its left are written
    by the client and would let anyone pick a fresh rate-limit key per request."""
    peer = request.client.host if request.client else "unknown"
    return forwarded_client(request.headers.get("x-forwarded-for"), peer, get_settings().trusted_proxy_hops)


def forwarded_client(header: str | None, peer: str, hops: int) -> str:
    if not header or hops <= 0:
        return peer
    entries = [e.strip() for e in header.split(",") if e.strip()]
    if not entries:
        return peer
    # With one proxy, its own entry (the client it saw) is the last one.
    return entries[-hops] if len(entries) >= hops else entries[0]


def visitor_location(request: Request) -> str:
    """City/country from the CDN's geo headers, when Ping sits behind one."""
    h = request.headers
    city = h.get("cf-ipcity") or h.get("x-vercel-ip-city") or ""
    country = h.get("cf-ipcountry") or h.get("x-vercel-ip-country") or h.get("x-country-code") or ""
    return ", ".join(p for p in (city, country) if p)[:120]
