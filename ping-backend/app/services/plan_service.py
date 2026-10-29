"""Plans live in the `plans` table and are managed from ping-admin.

Limits are copied onto the organization row when a plan is applied, so quota
checks never join `plans` and a custom deal can override any single limit."""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.db.models import Organization, Plan

MODEL_TIERS = ("fast", "balanced", "best")
LIMIT_FIELDS = ("messages_limit", "bots_limit", "sources_limit", "members_limit", "shares_limit", "remove_branding")
EDITABLE_FIELDS = (
    "name", "description", "price_monthly", "price_label", *LIMIT_FIELDS, "model_tiers", "features",
    "is_public", "is_default", "highlighted", "sort_order", "active",
)


def list_plans(db: Session, public_only: bool = False) -> list[Plan]:
    q = select(Plan).order_by(Plan.sort_order, Plan.created_at)
    if public_only:
        q = q.where(Plan.is_public.is_(True), Plan.active.is_(True))
    return list(db.scalars(q).all())


def get_plan(db: Session, key: str) -> Plan | None:
    return db.scalar(select(Plan).where(Plan.key == key))


def require_plan(db: Session, key: str) -> Plan:
    plan = get_plan(db, key)
    if plan is None:
        raise NotFoundError(f"Plan '{key}' not found")
    return plan


def default_plan(db: Session) -> Plan:
    plan = db.scalar(select(Plan).where(Plan.is_default.is_(True), Plan.active.is_(True)).limit(1))
    if plan is None:
        raise NotFoundError("No default plan is configured; set one in ping-admin")
    return plan


def allowed_tiers(db: Session, org: Organization | None) -> list[str]:
    plan = get_plan(db, org.plan) if org else None
    return list(plan.model_tiers) if plan else ["fast"]


def can_upgrade(db: Session, org: Organization) -> bool:
    current = get_plan(db, org.plan)
    floor = current.sort_order if current else -1
    return bool(db.scalar(
        select(func.count(Plan.id)).where(
            Plan.is_public.is_(True), Plan.active.is_(True), Plan.sort_order > floor
        )
    ))


def org_count(db: Session, key: str) -> int:
    return db.scalar(select(func.count(Organization.id)).where(Organization.plan == key)) or 0


def _validate(values: dict) -> None:
    tiers = values.get("model_tiers")
    if tiers is not None:
        if not tiers or any(t not in MODEL_TIERS for t in tiers):
            raise ValidationError(f"model_tiers must be a non-empty subset of {list(MODEL_TIERS)}")
    for field in ("messages_limit", "bots_limit", "sources_limit", "members_limit", "shares_limit"):
        if field in values and values[field] is not None and values[field] < 0:
            raise ValidationError(f"{field} cannot be negative")


def _apply_flags(db: Session, plan: Plan) -> None:
    if plan.is_default:
        if not plan.active:
            raise ValidationError("The default plan cannot be archived")
        db.execute(update(Plan).where(Plan.id != plan.id).values(is_default=False))


def create_plan(db: Session, values: dict) -> Plan:
    key = (values.get("key") or "").strip().lower()
    if not key or not key.replace("-", "").replace("_", "").isalnum():
        raise ValidationError("key must be letters, numbers, '-' or '_'")
    if get_plan(db, key) is not None:
        raise ConflictError(f"A plan with key '{key}' already exists")
    _validate(values)
    plan = Plan(key=key, **{k: v for k, v in values.items() if k in EDITABLE_FIELDS and v is not None})
    db.add(plan)
    db.flush()
    _apply_flags(db, plan)
    db.commit()
    return plan


def update_plan(db: Session, plan: Plan, values: dict, apply_to_existing: bool = False) -> Plan:
    _validate(values)
    if values.get("is_default") is False and plan.is_default:
        raise ValidationError("Mark another plan as default instead of unsetting this one")
    for field, value in values.items():
        if field in EDITABLE_FIELDS:
            setattr(plan, field, value)
    _apply_flags(db, plan)
    if apply_to_existing:
        db.execute(
            update(Organization)
            .where(Organization.plan == plan.key)
            .values(**{f: getattr(plan, f) for f in LIMIT_FIELDS})
        )
    db.commit()
    return plan


def apply_plan(db: Session, org: Organization, key: str, overrides: dict | None = None) -> None:
    """Put the org on `key` and copy its limits; `overrides` set custom values."""
    plan = require_plan(db, key)
    if not plan.active:
        raise ValidationError(f"Plan '{key}' is archived")
    limits = {f: getattr(plan, f) for f in LIMIT_FIELDS}
    if overrides:
        limits.update({k: v for k, v in overrides.items() if k in limits and v is not None})
    org.plan = plan.key
    for field, value in limits.items():
        setattr(org, field, value)


def to_public(plan: Plan) -> dict:
    return {
        "key": plan.key,
        "name": plan.name,
        "description": plan.description,
        "price_monthly": plan.price_monthly,
        "price_label": plan.price_label,
        "messages_limit": plan.messages_limit,
        "bots_limit": plan.bots_limit,
        "sources_limit": plan.sources_limit,
        "members_limit": plan.members_limit,
        "shares_limit": plan.shares_limit,
        "remove_branding": plan.remove_branding,
        "model_tiers": plan.model_tiers,
        "features": plan.features,
        "highlighted": plan.highlighted,
        "sort_order": plan.sort_order,
    }


def to_admin(db: Session, plan: Plan) -> dict:
    return {
        **to_public(plan),
        "id": plan.id,
        "is_public": plan.is_public,
        "is_default": plan.is_default,
        "active": plan.active,
        "org_count": org_count(db, plan.key),
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
    }
