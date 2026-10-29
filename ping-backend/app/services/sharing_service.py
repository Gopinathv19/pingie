"""Workspace members, bot shares, and the invitations that create them.

An invite is a link with a random token (only its sha256 is stored). The
invitee signs in with the invited email and accepts or declines. Seats are
checked when inviting (members + pending invites) and again when accepting.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, PermissionError_, QuotaExceededError, ValidationError
from app.db.models import Bot, BotShare, Invitation, Organization, OrganizationMember, Users
from app.services import bot_service, notify
from app.services.access_service import INVITABLE_ROLES
from app.services.auth_service import normalize_email

INVITE_TTL = timedelta(days=7)


def _now() -> datetime:
    return datetime.now(UTC)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def invite_url(token: str) -> str:
    return f"{get_settings().app_url.rstrip('/')}/invite/{token}"


def _mask(email: str) -> str:
    name, _, domain = email.partition("@")
    return f"{name[:1]}…@{domain}"


def _check_role(role: str) -> None:
    if role not in INVITABLE_ROLES:
        raise ValidationError("role must be 'editor' or 'viewer'")


# --- Counts -------------------------------------------------------------------------

def member_count(db: Session, org_id: uuid.UUID) -> int:
    return db.scalar(select(func.count(OrganizationMember.id)).where(OrganizationMember.organization_id == org_id)) or 0


def share_count(db: Session, bot_id: uuid.UUID) -> int:
    return db.scalar(select(func.count(BotShare.id)).where(BotShare.bot_id == bot_id)) or 0


def _pending(db: Session, *conditions):
    return select(Invitation).where(Invitation.status == "pending", Invitation.expires_at > _now(), *conditions)


def _pending_count(db: Session, *conditions) -> int:
    return db.scalar(select(func.count()).select_from(_pending(db, *conditions).subquery())) or 0


def _seat_error(limit: int, what: str) -> QuotaExceededError:
    return QuotaExceededError(
        f"Your plan allows {limit} {what}. Email {get_settings().support_email} to upgrade your plan."
    )


# --- Creating invites ---------------------------------------------------------------

def _new_invite(db: Session, *, email: str, kind: str, org: Organization, bot: Bot | None, role: str,
                inviter: Users) -> tuple[Invitation, str]:
    token = secrets.token_urlsafe(32)
    inv = Invitation(
        token_hash=_hash(token), email=email, kind=kind, organization_id=org.id,
        bot_id=bot.id if bot else None, role=role, invited_by_user_id=inviter.id,
        expires_at=_now() + INVITE_TTL,
    )
    db.add(inv)
    db.commit()
    target = f"the bot “{bot.name}”" if bot else f"the workspace “{org.name}”"
    notify.send_invitation(email, inviter.name or inviter.email, target, role, invite_url(token))
    return inv, token


def _assert_not_already_pending(db: Session, email: str, *conditions) -> None:
    if _pending_count(db, Invitation.email == email, *conditions):
        raise ConflictError(f"An invite is already pending for {email}")


def invite_to_workspace(db: Session, org: Organization, inviter: Users, email: str, role: str):
    _check_role(role)
    email = normalize_email(email)
    if email == inviter.email:
        raise ConflictError("You already have access to this workspace")
    existing = db.scalar(
        select(OrganizationMember.id)
        .join(Users, Users.id == OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == org.id, Users.email == email)
    )
    if existing:
        raise ConflictError(f"{email} is already a member of this workspace")
    ws = (Invitation.kind == "workspace", Invitation.organization_id == org.id)
    _assert_not_already_pending(db, email, *ws)
    if member_count(db, org.id) + _pending_count(db, *ws) >= org.members_limit:
        raise _seat_error(org.members_limit, "workspace members")
    return _new_invite(db, email=email, kind="workspace", org=org, bot=None, role=role, inviter=inviter)


def invite_to_bot(db: Session, bot: Bot, inviter: Users, email: str, role: str):
    _check_role(role)
    email = normalize_email(email)
    org = db.get(Organization, bot.organization_id)
    user = db.scalar(select(Users).where(Users.email == email))
    if email == inviter.email:
        raise ConflictError("You already have access to this bot")
    if user is not None:
        if db.scalar(select(OrganizationMember.id).where(
            OrganizationMember.organization_id == org.id, OrganizationMember.user_id == user.id
        )):
            raise ConflictError(f"{email} already has access through the workspace")
        if db.scalar(select(BotShare.id).where(BotShare.bot_id == bot.id, BotShare.user_id == user.id)):
            raise ConflictError(f"This bot is already shared with {email}")
    b = (Invitation.kind == "bot", Invitation.bot_id == bot.id)
    _assert_not_already_pending(db, email, *b)
    if share_count(db, bot.id) + _pending_count(db, *b) >= org.shares_limit:
        raise _seat_error(org.shares_limit, "people per shared bot")
    return _new_invite(db, email=email, kind="bot", org=org, bot=bot, role=role, inviter=inviter)


def resend(db: Session, inv: Invitation) -> str:
    """A fresh link (the old one stops working) and a fresh 7 days."""
    if inv.status != "pending":
        raise ConflictError("Only pending invites can be resent")
    token = secrets.token_urlsafe(32)
    inv.token_hash = _hash(token)
    inv.expires_at = _now() + INVITE_TTL
    db.commit()
    org = db.get(Organization, inv.organization_id)
    bot = db.get(Bot, inv.bot_id) if inv.bot_id else None
    inviter = db.get(Users, inv.invited_by_user_id) if inv.invited_by_user_id else None
    target = f"the bot “{bot.name}”" if bot else f"the workspace “{org.name}”"
    notify.send_invitation(inv.email, inviter.name if inviter else "A teammate", target, inv.role, invite_url(token))
    return token


def get_invite_for(db: Session, inv_id: uuid.UUID, *, org_id: uuid.UUID | None = None,
                   bot_id: uuid.UUID | None = None) -> Invitation:
    inv = db.get(Invitation, inv_id)
    if inv is None or (org_id and (inv.organization_id != org_id or inv.kind != "workspace")) or (
        bot_id and inv.bot_id != bot_id
    ):
        raise NotFoundError("Invite not found")
    return inv


def revoke(db: Session, inv: Invitation) -> None:
    if inv.status == "pending":
        inv.status = "revoked"
        db.commit()


# --- Members and shares -------------------------------------------------------------

def _person(user: Users) -> dict:
    return {"user_id": user.id, "email": user.email, "name": user.name, "avatar_url": user.avatar_url}


def invite_to_read(db: Session, inv: Invitation) -> dict:
    org = db.get(Organization, inv.organization_id)
    bot = db.get(Bot, inv.bot_id) if inv.bot_id else None
    inviter = db.get(Users, inv.invited_by_user_id) if inv.invited_by_user_id else None
    return {
        "id": inv.id,
        "email": inv.email,
        "kind": inv.kind,
        "role": inv.role,
        "status": "expired" if inv.status == "pending" and inv.expires_at <= _now() else inv.status,
        "organization_id": inv.organization_id,
        "organization_name": org.name if org else "",
        "bot_id": bot.public_id if bot else None,
        "bot_name": bot.name if bot else None,
        "invited_by": (inviter.name or inviter.email) if inviter else None,
        "expires_at": inv.expires_at,
        "created_at": inv.created_at,
    }


def list_members(db: Session, org: Organization) -> dict:
    rows = db.execute(
        select(Users, OrganizationMember.role, OrganizationMember.created_at)
        .join(OrganizationMember, OrganizationMember.user_id == Users.id)
        .where(OrganizationMember.organization_id == org.id)
        .order_by(OrganizationMember.created_at)
    ).all()
    invites = db.scalars(
        _pending(db, Invitation.kind == "workspace", Invitation.organization_id == org.id)
        .order_by(Invitation.created_at)
    ).all()
    return {
        "members": [{**_person(u), "role": role, "joined_at": at} for u, role, at in rows],
        "invitations": [invite_to_read(db, i) for i in invites],
        "seats_used": len(rows) + len(invites),
        "seats_limit": org.members_limit,
    }


def _member_row(db: Session, org: Organization, user_id: uuid.UUID) -> OrganizationMember:
    row = db.scalar(select(OrganizationMember).where(
        OrganizationMember.organization_id == org.id, OrganizationMember.user_id == user_id
    ))
    if row is None:
        raise NotFoundError("Member not found")
    if row.role == "owner":
        raise PermissionError_("The workspace owner can't be changed or removed")
    return row


def set_member_role(db: Session, org: Organization, user_id: uuid.UUID, role: str) -> None:
    _check_role(role)
    _member_row(db, org, user_id).role = role
    db.commit()


def remove_member(db: Session, org: Organization, user_id: uuid.UUID) -> None:
    db.delete(_member_row(db, org, user_id))
    db.commit()


def list_shares(db: Session, bot: Bot) -> dict:
    org = db.get(Organization, bot.organization_id)
    rows = db.execute(
        select(Users, BotShare.role, BotShare.created_at)
        .join(BotShare, BotShare.user_id == Users.id)
        .where(BotShare.bot_id == bot.id)
        .order_by(BotShare.created_at)
    ).all()
    invites = db.scalars(
        _pending(db, Invitation.kind == "bot", Invitation.bot_id == bot.id).order_by(Invitation.created_at)
    ).all()
    return {
        "shares": [{**_person(u), "role": role, "joined_at": at} for u, role, at in rows],
        "invitations": [invite_to_read(db, i) for i in invites],
        "seats_used": len(rows) + len(invites),
        "seats_limit": org.shares_limit if org else 0,
    }


def _share_row(db: Session, bot: Bot, user_id: uuid.UUID) -> BotShare:
    row = db.scalar(select(BotShare).where(BotShare.bot_id == bot.id, BotShare.user_id == user_id))
    if row is None:
        raise NotFoundError("Share not found")
    return row


def set_share_role(db: Session, bot: Bot, user_id: uuid.UUID, role: str) -> None:
    _check_role(role)
    _share_row(db, bot, user_id).role = role
    db.commit()


def remove_share(db: Session, bot: Bot, user_id: uuid.UUID) -> None:
    db.delete(_share_row(db, bot, user_id))
    db.commit()


def shared_bots(db: Session, user: Users) -> list[dict]:
    rows = db.execute(
        select(Bot, BotShare.role, Organization.name, Users.name, Users.email)
        .join(BotShare, BotShare.bot_id == Bot.id)
        .join(Organization, Organization.id == Bot.organization_id)
        .outerjoin(Users, Users.id == BotShare.invited_by_user_id)
        .where(BotShare.user_id == user.id)
        .order_by(BotShare.created_at)
    ).all()
    cards = {c["id"]: c for c in bot_service.summaries(db, [r[0] for r in rows])}
    return [
        {**cards[bot.public_id], "role": role, "organization_name": org_name, "shared_by": by_name or by_email}
        for bot, role, org_name, by_name, by_email in rows
    ]


# --- The invitee's side ---------------------------------------------------------------

def invites_for(db: Session, user: Users) -> list[dict]:
    invites = db.scalars(_pending(db, Invitation.email == user.email).order_by(Invitation.created_at)).all()
    return [invite_to_read(db, i) for i in invites]


def by_token(db: Session, token: str) -> Invitation:
    inv = db.scalar(select(Invitation).where(Invitation.token_hash == _hash(token)))
    if inv is None:
        raise NotFoundError("This invite link is invalid or has been replaced by a newer one")
    return inv


def mine(db: Session, user: Users, inv_id: uuid.UUID) -> Invitation:
    inv = db.get(Invitation, inv_id)
    if inv is None or inv.email != user.email:
        raise NotFoundError("Invite not found")
    return inv


def preview(db: Session, inv: Invitation, user: Users | None) -> dict:
    data = invite_to_read(db, inv)
    data["email"] = _mask(inv.email)
    data["email_matches"] = bool(user and user.email == inv.email)
    return data


def _assert_open(inv: Invitation, user: Users) -> None:
    if inv.email != user.email:
        raise PermissionError_(f"This invite was sent to {_mask(inv.email)}. Sign in with that Google account.")
    if inv.status != "pending":
        raise ConflictError(f"This invite was already {inv.status}")
    if inv.expires_at <= _now():
        raise ConflictError("This invite has expired. Ask for a new one.")


def accept(db: Session, inv: Invitation, user: Users) -> dict:
    _assert_open(inv, user)
    org = db.get(Organization, inv.organization_id)
    if inv.kind == "workspace":
        if not db.scalar(select(OrganizationMember.id).where(
            OrganizationMember.organization_id == org.id, OrganizationMember.user_id == user.id
        )):
            if member_count(db, org.id) >= org.members_limit:
                raise _seat_error(org.members_limit, "workspace members")
            db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=inv.role))
    else:
        bot = db.get(Bot, inv.bot_id)
        if bot is None:
            raise NotFoundError("This bot no longer exists")
        if not db.scalar(select(BotShare.id).where(BotShare.bot_id == bot.id, BotShare.user_id == user.id)):
            if share_count(db, bot.id) >= org.shares_limit:
                raise _seat_error(org.shares_limit, "people per shared bot")
            db.add(BotShare(bot_id=bot.id, user_id=user.id, role=inv.role, invited_by_user_id=inv.invited_by_user_id))
    inv.status = "accepted"
    inv.accepted_at = _now()
    db.commit()
    return invite_to_read(db, inv)


def decline(db: Session, inv: Invitation, user: Users) -> dict:
    _assert_open(inv, user)
    inv.status = "declined"
    db.commit()
    return invite_to_read(db, inv)
