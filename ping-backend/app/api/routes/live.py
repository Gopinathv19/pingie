"""An agent's presence and the live chats waiting for them."""

from fastapi import APIRouter, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, DbSession
from app.services import live_service

router = APIRouter(prefix="/me", tags=["live"])


class Presence(BaseModel):
    available: bool


@router.post("/presence", status_code=status.HTTP_204_NO_CONTENT)
def heartbeat(payload: Presence, db: DbSession, user: CurrentUser) -> None:
    """Sent every ~30 s by an open dashboard tab."""
    live_service.heartbeat(db, user, payload.available)


@router.get("/live")
def live(db: DbSession, user: CurrentUser):
    """Chats waiting for a person on any bot this user can edit, and their own."""
    return live_service.live_summary(db, user)
