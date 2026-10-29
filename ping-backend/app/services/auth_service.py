"""Google sign-in and dashboard users. Same flow as Memora's console login:
the frontend sends a Google ID token, the backend verifies it with Google's
tokeninfo endpoint, and a session JWT goes back as an HttpOnly cookie."""

import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AuthenticationError
from app.db.models import AuthenticatedUser, Users

GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


@dataclass
class GoogleIdentity:
    provider_user_id: str
    email: str
    email_verified: bool
    name: str
    avatar_url: str


def normalize_email(email: str) -> str:
    return email.strip().lower()


def verify_google_id_token(id_token: str) -> GoogleIdentity:
    settings = get_settings()
    if not settings.google_client_id:
        raise AuthenticationError("Google sign-in is not configured: set GOOGLE_CLIENT_ID in ping-backend/.env")
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(GOOGLE_TOKENINFO_URL, params={"id_token": id_token})
    except httpx.HTTPError as exc:
        raise AuthenticationError("Could not reach Google to verify sign-in") from exc
    if response.status_code != 200:
        raise AuthenticationError("Invalid Google identity token")

    data = response.json()
    if str(data.get("aud", "")) != settings.google_client_id:
        raise AuthenticationError("Google token audience does not match this app")
    provider_user_id = str(data.get("sub", ""))
    email_verified = str(data.get("email_verified", "")).lower() == "true"
    if not provider_user_id or not email_verified:
        raise AuthenticationError("Google account email must be verified")
    return GoogleIdentity(
        provider_user_id=provider_user_id,
        email=normalize_email(str(data.get("email", ""))),
        email_verified=email_verified,
        name=str(data.get("name", "")),
        avatar_url=str(data.get("picture", "")),
    )


def get_user(db: Session, user_id: uuid.UUID) -> Users | None:
    return db.get(Users, user_id)


def find_user_by_email(db: Session, email: str) -> Users | None:
    return db.scalar(select(Users).where(Users.email == normalize_email(email)))


def create_user(db: Session, email: str, email_verified: bool, name: str = "", avatar_url: str = "") -> Users:
    user = Users(email=normalize_email(email), email_verified=email_verified, name=name, avatar_url=avatar_url)
    db.add(user)
    db.flush()
    return user


def login_with_google(db: Session, id_token: str) -> Users:
    identity = verify_google_id_token(id_token)
    return login_with_identity(db, identity)


def login_with_identity(db: Session, identity: GoogleIdentity) -> Users:
    """Find or create the user behind a verified Google identity. The first
    sign-in also creates the user's organization."""
    from app.services import organization_service

    link = db.scalar(
        select(AuthenticatedUser).where(
            AuthenticatedUser.provider == "google",
            AuthenticatedUser.provider_user_id == identity.provider_user_id,
        )
    )
    if link is not None:
        user = db.get(Users, link.user_id)
    else:
        user = find_user_by_email(db, identity.email)
        if user is None:
            user = create_user(db, identity.email, identity.email_verified, identity.name, identity.avatar_url)
        db.add(AuthenticatedUser(user_id=user.id, provider="google", provider_user_id=identity.provider_user_id))

    # Profile details follow the Google account.
    user.name = identity.name or user.name
    user.avatar_url = identity.avatar_url or user.avatar_url
    user.email_verified = user.email_verified or identity.email_verified
    if user.status != "active":
        raise AuthenticationError("This account is disabled")

    organization_service.ensure_personal_organization(db, user)
    db.commit()
    return user
