"""Session tokens, widget conversation tokens and public identifiers."""

import secrets
import string
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import get_settings
from app.core.errors import AuthenticationError

_ALPHABET = string.ascii_lowercase + string.digits


def new_public_id(prefix: str, length: int = 7) -> str:
    """Short, URL-safe public id such as `bot_7f3k2a9`."""
    return prefix + "".join(secrets.choice(_ALPHABET) for _ in range(length))


def new_public_key() -> str:
    return "pk_live_" + secrets.token_urlsafe(12).replace("-", "").replace("_", "")[:16]


# --- Dashboard session ----------------------------------------------------------

def create_session_token(user_id: uuid.UUID, email: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iss": settings.auth_jwt_issuer,
        "typ": "session",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.auth_token_ttl_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.auth_jwt_secret, algorithm="HS256")


def session_user_id(token: str) -> uuid.UUID:
    payload = _decode(token, "session", "Invalid or expired session")
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("Invalid or expired session") from exc


# --- Admin console ----------------------------------------------------------------
# Signed with a separate secret so a leaked dashboard secret can't mint admin tokens.

def create_admin_token(email: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": email,
        "iss": settings.auth_jwt_issuer,
        "typ": "admin",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.admin_token_ttl_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.admin_jwt_secret, algorithm="HS256")


def admin_email_from_token(token: str) -> str:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.admin_jwt_secret,
            algorithms=["HS256"],
            issuer=settings.auth_jwt_issuer,
            options={"require": ["exp", "iat", "sub", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Admin session expired, sign in again") from exc
    email = str(payload.get("sub", "")).lower()
    if payload.get("typ") != "admin" or email not in settings.admin_email_list:
        raise AuthenticationError("Admin session expired, sign in again")
    return email


# --- Widget conversation --------------------------------------------------------
#
# A visitor proves a conversation is theirs with a token issued when it was
# started. Conversation ids are UUIDs, but the token keeps one visitor from
# reading or writing another's chat even if an id leaks.

def create_conversation_token(conversation_id: uuid.UUID, bot_id: uuid.UUID) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(conversation_id),
        "bot": str(bot_id),
        "iss": settings.auth_jwt_issuer,
        "typ": "conversation",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=settings.widget_conversation_ttl_hours)).timestamp()),
    }
    return jwt.encode(payload, settings.auth_jwt_secret, algorithm="HS256")


def conversation_from_token(token: str, bot_id: uuid.UUID) -> uuid.UUID:
    payload = _decode(token, "conversation", "Invalid or expired conversation token")
    if payload.get("bot") != str(bot_id):
        raise AuthenticationError("Invalid or expired conversation token")
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("Invalid or expired conversation token") from exc


def _decode(token: str, typ: str, message: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.auth_jwt_secret,
            algorithms=["HS256"],
            issuer=settings.auth_jwt_issuer,
            options={"require": ["exp", "iat", "sub", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise AuthenticationError(message) from exc
    if payload.get("typ") != typ:
        raise AuthenticationError(message)
    return payload
