"""Public plan catalogue, shown on the pricing page and upgrade modal."""

from fastapi import APIRouter

from app.api.deps import DbSession
from app.services import plan_service

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("")
def list_public_plans(db: DbSession) -> list[dict]:
    return [plan_service.to_public(p) for p in plan_service.list_plans(db, public_only=True)]
