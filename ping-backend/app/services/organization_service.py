"""Organizations, membership and plan usage."""

import re
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import NotFoundError, QuotaExceededError
from app.db.models import Bot, Message, Organization, OrganizationMember, Users
from app.services import plan_service


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "workspace"
    return f"{slug}-{secrets.token_hex(3)}"


def ensure_personal_organization(db: Session, user: Users) -> Organization:
    """Every user has at least one organization; the first sign-in makes it."""
    existing = db.scalar(
        select(Organization)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user.id)
        .limit(1)
    )
    if existing is not None:
        return existing
    first = (user.name or user.email.split("@")[0]).split()[0]
    org = Organization(name=f"{first}'s workspace", slug=_slugify(first), owner_user_id=user.id)
    plan_service.apply_plan(db, org, plan_service.default_plan(db).key)
    db.add(org)
    db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
    db.flush()
    return org


def list_for_user(db: Session, user: Users) -> list[tuple[Organization, str]]:
    rows = db.execute(
        select(Organization, OrganizationMember.role)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user.id, Organization.status == "active")
        # Your own workspace first, then ones you were invited to.
        .order_by((OrganizationMember.role != "owner"), Organization.created_at)
    ).all()
    return [(org, role) for org, role in rows]


def require_member(db: Session, user: Users, organization_id: uuid.UUID) -> tuple[Organization, str]:
    """The organization if the user belongs to it. Otherwise 404, never 403:
    an outsider learns nothing about which ids exist."""
    row = db.execute(
        select(Organization, OrganizationMember.role)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(
            Organization.id == organization_id, OrganizationMember.user_id == user.id,
            Organization.status == "active",  # a suspended workspace is out of reach
        )
    ).first()
    if row is None:
        raise NotFoundError("Organization not found")
    return row[0], row[1]


def _month_start() -> datetime:
    now = datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def messages_this_month(db: Session, organization_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count(Message.id))
        .join(Bot, Bot.id == Message.bot_id)
        .where(
            Bot.organization_id == organization_id,
            Message.created_at >= _month_start(),
            # Agent replies and status notes aren't bot usage.
            Message.role.in_(("visitor", "bot")),
        )
    ) or 0


def bot_count(db: Session, organization_id: uuid.UUID) -> int:
    return db.scalar(select(func.count(Bot.id)).where(Bot.organization_id == organization_id)) or 0


def usage(db: Session, org: Organization) -> dict:
    return {
        "messages_used": messages_this_month(db, org.id),
        "messages_limit": org.messages_limit,
        "bots_used": bot_count(db, org.id),
        "bots_limit": org.bots_limit,
        "sources_limit": org.sources_limit,
        "members_limit": org.members_limit,
        "shares_limit": org.shares_limit,
        "remove_branding": org.remove_branding,
        "custom_design": org.custom_design,
    }


def upgrade_plan(db: Session, org: Organization, plan: str, overrides: dict | None = None) -> Organization:
    """Change the org's plan and update all denormalized limit columns."""
    plan_service.apply_plan(db, org, plan, overrides)
    db.commit()
    return org


def assert_message_quota(db: Session, organization_id: uuid.UUID) -> None:
    org = db.get(Organization, organization_id)
    if org is not None and messages_this_month(db, org.id) >= org.messages_limit:
        settings = get_settings()
        raise QuotaExceededError(
            f"This workspace has used its monthly message allowance. "
            f"Email {settings.support_email} to upgrade your plan."
        )


def to_read(db: Session, org: Organization, role: str) -> dict:
    plan = plan_service.get_plan(db, org.plan)
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "plan": org.plan.upper(),
        "plan_name": plan.name if plan else org.plan.title(),
        "can_upgrade": plan_service.can_upgrade(db, org),
        "allowed_model_tiers": list(plan.model_tiers) if plan else ["fast"],
        "role": role,
        "initial": (org.name[:1] or "?").upper(),
        "usage": usage(db, org),
    }


def rename(db: Session, org: Organization, name: str) -> Organization:
    org.name = name.strip()
    db.commit()
    return org
