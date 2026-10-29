"""Internal admin API used by ping-admin.

Admins sign in with Google; only emails in ADMIN_EMAILS get an admin token.
Every other route requires that token as `Authorization: Bearer <token>`.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import DbSession
from app.core.config import get_settings
from app.core.errors import AuthenticationError, NotFoundError, PermissionError_
from app.core.security import admin_email_from_token, create_admin_token
from app.db.models import Organization, Users
from app.services import auth_service, organization_service, plan_service

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(authorization: Annotated[str | None, Header()] = None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthenticationError("Admin sign-in required")
    return admin_email_from_token(token.strip())


AdminEmail = Annotated[str, Depends(require_admin)]


# --- Auth -------------------------------------------------------------------------

class GoogleLogin(BaseModel):
    id_token: str = Field(min_length=10)


@router.post("/auth/google")
def admin_google_login(payload: GoogleLogin):
    identity = auth_service.verify_google_id_token(payload.id_token)
    if identity.email not in get_settings().admin_email_list:
        raise PermissionError_(f"{identity.email} is not an admin")
    return {"token": create_admin_token(identity.email), "email": identity.email}


@router.get("/me")
def admin_me(email: AdminEmail):
    return {"email": email}


# --- Organizations ------------------------------------------------------------------

def _org_row(db: Session, org: Organization) -> dict:
    owner = db.get(Users, org.owner_user_id)
    plan = plan_service.get_plan(db, org.plan)
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "plan": org.plan,
        "plan_name": plan.name if plan else org.plan,
        "plan_paid": bool(plan and plan.price_monthly != 0),
        "owner_email": owner.email if owner else None,
        "owner_name": owner.name if owner else None,
        "messages_used": organization_service.messages_this_month(db, org.id),
        "messages_limit": org.messages_limit,
        "bots_used": organization_service.bot_count(db, org.id),
        "bots_limit": org.bots_limit,
        "sources_limit": org.sources_limit,
        "members_limit": org.members_limit,
        "shares_limit": org.shares_limit,
        "remove_branding": org.remove_branding,
        "stripe_customer_id": org.stripe_customer_id,
        "created_at": org.created_at,
        "status": org.status,
    }


def _require_org(db: Session, org_id: uuid.UUID) -> Organization:
    org = db.get(Organization, org_id)
    if org is None:
        raise NotFoundError("Organization not found")
    return org


@router.get("/orgs")
def list_orgs(db: DbSession, _: AdminEmail, search: str | None = None):
    q = select(Organization).order_by(Organization.created_at.desc())
    if search:
        term = f"%{search.lower()}%"
        owner_ids = select(Users.id).where(Users.email.ilike(term) | Users.name.ilike(term))
        q = q.where(
            Organization.name.ilike(term)
            | Organization.slug.ilike(term)
            | Organization.owner_user_id.in_(owner_ids)
        )
    return [_org_row(db, org) for org in db.scalars(q).all()]


@router.get("/orgs/{org_id}")
def get_org(org_id: uuid.UUID, db: DbSession, _: AdminEmail):
    return _org_row(db, _require_org(db, org_id))


class OrgPlanUpdate(BaseModel):
    plan: str
    messages_limit: int | None = Field(default=None, ge=0)
    bots_limit: int | None = Field(default=None, ge=0)
    sources_limit: int | None = Field(default=None, ge=0)
    members_limit: int | None = Field(default=None, ge=0)
    shares_limit: int | None = Field(default=None, ge=0)
    remove_branding: bool | None = None


@router.patch("/orgs/{org_id}/plan")
def update_org_plan(org_id: uuid.UUID, payload: OrgPlanUpdate, db: DbSession, _: AdminEmail):
    org = _require_org(db, org_id)
    overrides = payload.model_dump(exclude={"plan"}, exclude_none=True)
    organization_service.upgrade_plan(db, org, payload.plan, overrides or None)
    return _org_row(db, org)


# --- Plans ----------------------------------------------------------------------------

class PlanFields(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    price_monthly: int | None = Field(default=None, ge=0)
    price_label: str | None = Field(default=None, max_length=40)
    messages_limit: int | None = Field(default=None, ge=0)
    bots_limit: int | None = Field(default=None, ge=0)
    sources_limit: int | None = Field(default=None, ge=0)
    members_limit: int | None = Field(default=None, ge=0)
    shares_limit: int | None = Field(default=None, ge=0)
    remove_branding: bool | None = None
    model_tiers: list[str] | None = None
    features: list[str] | None = None
    is_public: bool | None = None
    is_default: bool | None = None
    highlighted: bool | None = None
    sort_order: int | None = None
    active: bool | None = None


class PlanCreate(PlanFields):
    key: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=80)
    messages_limit: int = Field(ge=0)
    bots_limit: int = Field(ge=0)
    sources_limit: int = Field(ge=0)
    members_limit: int = Field(ge=0)


class PlanUpdate(PlanFields):
    apply_to_existing: bool = False


@router.get("/plans")
def admin_list_plans(db: DbSession, _: AdminEmail):
    return [plan_service.to_admin(db, p) for p in plan_service.list_plans(db)]


@router.get("/plans/{key}")
def admin_get_plan(key: str, db: DbSession, _: AdminEmail):
    return plan_service.to_admin(db, plan_service.require_plan(db, key))


@router.post("/plans", status_code=201)
def admin_create_plan(payload: PlanCreate, db: DbSession, _: AdminEmail):
    plan = plan_service.create_plan(db, payload.model_dump(exclude_none=True))
    return plan_service.to_admin(db, plan)


@router.patch("/plans/{key}")
def admin_update_plan(key: str, payload: PlanUpdate, db: DbSession, _: AdminEmail):
    plan = plan_service.require_plan(db, key)
    values = payload.model_dump(exclude_unset=True, exclude={"apply_to_existing"})
    values = {k: v for k, v in values.items() if v is not None or k == "price_monthly"}
    plan = plan_service.update_plan(db, plan, values, apply_to_existing=payload.apply_to_existing)
    return plan_service.to_admin(db, plan)
