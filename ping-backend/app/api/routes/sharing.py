"""Workspace members, bot sharing, and invitations."""

import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel, EmailStr

from app.api.deps import CurrentUser, DbSession, OptionalUser, OwnedBot
from app.services import organization_service, sharing_service
from app.services.access_service import bot_access, require_org_role

router = APIRouter(tags=["sharing"])


class InviteCreate(BaseModel):
    email: EmailStr
    role: str = "viewer"


class RoleUpdate(BaseModel):
    role: str


def _created(db, inv, token) -> dict:
    return {**sharing_service.invite_to_read(db, inv), "invite_url": sharing_service.invite_url(token)}


def _owned_org(db, user, org_id: uuid.UUID):
    org, role = organization_service.require_member(db, user, org_id)
    require_org_role(role, "owner")
    return org


# --- Workspace members -------------------------------------------------------------

@router.get("/orgs/{org_id}/members")
def list_members(org_id: uuid.UUID, db: DbSession, user: CurrentUser):
    org, _ = organization_service.require_member(db, user, org_id)
    return sharing_service.list_members(db, org)


@router.post("/orgs/{org_id}/invitations", status_code=status.HTTP_201_CREATED)
def invite_member(org_id: uuid.UUID, payload: InviteCreate, db: DbSession, user: CurrentUser):
    org = _owned_org(db, user, org_id)
    inv, token = sharing_service.invite_to_workspace(db, org, user, payload.email, payload.role)
    return _created(db, inv, token)


@router.post("/orgs/{org_id}/invitations/{inv_id}/resend")
def resend_member_invite(org_id: uuid.UUID, inv_id: uuid.UUID, db: DbSession, user: CurrentUser):
    _owned_org(db, user, org_id)
    inv = sharing_service.get_invite_for(db, inv_id, org_id=org_id)
    return _created(db, inv, sharing_service.resend(db, inv))


@router.delete("/orgs/{org_id}/invitations/{inv_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_member_invite(org_id: uuid.UUID, inv_id: uuid.UUID, db: DbSession, user: CurrentUser) -> None:
    _owned_org(db, user, org_id)
    sharing_service.revoke(db, sharing_service.get_invite_for(db, inv_id, org_id=org_id))


@router.delete("/orgs/{org_id}/members/me", status_code=status.HTTP_204_NO_CONTENT)
def leave_workspace(org_id: uuid.UUID, db: DbSession, user: CurrentUser) -> None:
    org, _ = organization_service.require_member(db, user, org_id)
    sharing_service.remove_member(db, org, user.id)


@router.patch("/orgs/{org_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def set_member_role(org_id: uuid.UUID, user_id: uuid.UUID, payload: RoleUpdate, db: DbSession, user: CurrentUser) -> None:
    sharing_service.set_member_role(db, _owned_org(db, user, org_id), user_id, payload.role)


@router.delete("/orgs/{org_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(org_id: uuid.UUID, user_id: uuid.UUID, db: DbSession, user: CurrentUser) -> None:
    sharing_service.remove_member(db, _owned_org(db, user, org_id), user_id)


# --- Bot shares ----------------------------------------------------------------------

@router.get("/bots/{bot_id}/shares")
def list_shares(bot: OwnedBot, db: DbSession):
    return sharing_service.list_shares(db, bot)


@router.post("/bots/{bot_id}/invitations", status_code=status.HTTP_201_CREATED)
def invite_to_bot(payload: InviteCreate, bot: OwnedBot, db: DbSession, user: CurrentUser):
    inv, token = sharing_service.invite_to_bot(db, bot, user, payload.email, payload.role)
    return _created(db, inv, token)


@router.post("/bots/{bot_id}/invitations/{inv_id}/resend")
def resend_bot_invite(inv_id: uuid.UUID, bot: OwnedBot, db: DbSession):
    inv = sharing_service.get_invite_for(db, inv_id, bot_id=bot.id)
    return _created(db, inv, sharing_service.resend(db, inv))


@router.delete("/bots/{bot_id}/invitations/{inv_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_bot_invite(inv_id: uuid.UUID, bot: OwnedBot, db: DbSession) -> None:
    sharing_service.revoke(db, sharing_service.get_invite_for(db, inv_id, bot_id=bot.id))


@router.patch("/bots/{bot_id}/shares/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def set_share_role(user_id: uuid.UUID, payload: RoleUpdate, bot: OwnedBot, db: DbSession) -> None:
    sharing_service.set_share_role(db, bot, user_id, payload.role)


@router.delete("/bots/{bot_id}/shares/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_share(user_id: uuid.UUID, bot: OwnedBot, db: DbSession) -> None:
    sharing_service.remove_share(db, bot, user_id)


@router.delete("/shared-bots/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
def leave_shared_bot(bot_id: str, db: DbSession, user: CurrentUser) -> None:
    """Remove a bot from your own "Shared with me" list."""
    access = bot_access(db, user, bot_id)
    if access.via == "share":
        sharing_service.remove_share(db, access.bot, user.id)


@router.get("/shared-bots")
def list_shared_bots(db: DbSession, user: CurrentUser):
    return sharing_service.shared_bots(db, user)


# --- The invitee's side -------------------------------------------------------------------

@router.get("/invitations/mine")
def my_invitations(db: DbSession, user: CurrentUser):
    return sharing_service.invites_for(db, user)


@router.post("/invitations/{inv_id}/accept")
def accept_mine(inv_id: uuid.UUID, db: DbSession, user: CurrentUser):
    return sharing_service.accept(db, sharing_service.mine(db, user, inv_id), user)


@router.post("/invitations/{inv_id}/decline")
def decline_mine(inv_id: uuid.UUID, db: DbSession, user: CurrentUser):
    return sharing_service.decline(db, sharing_service.mine(db, user, inv_id), user)


@router.get("/invitations/by-token/{token}")
def preview_invite(token: str, db: DbSession, user: OptionalUser):
    return sharing_service.preview(db, sharing_service.by_token(db, token), user)


@router.post("/invitations/by-token/{token}/accept")
def accept_by_token(token: str, db: DbSession, user: CurrentUser):
    return sharing_service.accept(db, sharing_service.by_token(db, token), user)


@router.post("/invitations/by-token/{token}/decline")
def decline_by_token(token: str, db: DbSession, user: CurrentUser):
    return sharing_service.decline(db, sharing_service.by_token(db, token), user)
