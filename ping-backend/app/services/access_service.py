"""Who may do what to a bot.

A user reaches a bot either as a member of its organization (`via=workspace`)
or through a direct share (`via=share`). Roles rank viewer < editor < owner.
No access at all is a 404, so outsiders learn nothing about which ids exist;
access with too low a role is a 403.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, PermissionError_
from app.db.models import Bot, BotShare, OrganizationMember, Users

ROLE_RANK = {"viewer": 1, "editor": 2, "owner": 3}
INVITABLE_ROLES = ("editor", "viewer")

_DENIED = {
    "editor": "Viewers can't change this bot. Ask the owner for edit access.",
    "owner": "Only the owner can do this.",
}


@dataclass
class BotAccess:
    bot: Bot
    role: str
    via: str  # "workspace" | "share"


def has_role(role: str, min_role: str) -> bool:
    return ROLE_RANK.get(role, 0) >= ROLE_RANK[min_role]


def bot_access(db: Session, user: Users, public_id: str) -> BotAccess:
    # One query for the bot and the user's workspace role (each query is a round trip).
    row = db.execute(
        select(Bot, OrganizationMember.role)
        .outerjoin(
            OrganizationMember,
            (OrganizationMember.organization_id == Bot.organization_id) & (OrganizationMember.user_id == user.id),
        )
        .where(Bot.public_id == public_id)
    ).first()
    if row is not None:
        bot, member_role = row
        if member_role:
            return BotAccess(bot, member_role, "workspace")
        share_role = db.scalar(select(BotShare.role).where(BotShare.bot_id == bot.id, BotShare.user_id == user.id))
        if share_role:
            return BotAccess(bot, share_role, "share")
    raise NotFoundError("Bot not found")


def require_bot_role(db: Session, user: Users, public_id: str, min_role: str) -> BotAccess:
    access = bot_access(db, user, public_id)
    if not has_role(access.role, min_role):
        raise PermissionError_(_DENIED.get(min_role, "You don't have permission to do this."))
    return access


def require_org_role(role: str, min_role: str) -> None:
    if not has_role(role, min_role):
        raise PermissionError_(
            "Only the workspace owner can do this." if min_role == "owner"
            else "Viewers can't make changes in this workspace."
        )
