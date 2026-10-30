"""Saved replies: canned answers agents insert in live chat ("/" in the reply box)."""

import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import CurrentBot, CurrentUser, DbSession, EditableBot
from app.core.errors import NotFoundError, ValidationError
from app.db.models import BotSavedReply

router = APIRouter(prefix="/bots/{bot_id}/saved-replies", tags=["saved replies"])

MAX_PER_BOT = 100


class SavedReplyIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=4000)


class SavedReplyPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    body: str | None = Field(default=None, min_length=1, max_length=4000)


def _read(r: BotSavedReply) -> dict:
    return {"id": r.id, "title": r.title, "body": r.body, "updated_at": r.updated_at}


def _get(db, bot, reply_id: uuid.UUID) -> BotSavedReply:
    row = db.get(BotSavedReply, reply_id)
    if row is None or row.bot_id != bot.id:
        raise NotFoundError("Saved reply not found")
    return row


@router.get("")
def list_replies(bot: CurrentBot, db: DbSession):
    rows = db.scalars(select(BotSavedReply).where(BotSavedReply.bot_id == bot.id).order_by(func.lower(BotSavedReply.title)))
    return [_read(r) for r in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def add_reply(payload: SavedReplyIn, bot: EditableBot, db: DbSession, user: CurrentUser):
    count = db.scalar(select(func.count()).select_from(BotSavedReply).where(BotSavedReply.bot_id == bot.id)) or 0
    if count >= MAX_PER_BOT:
        raise ValidationError(f"A bot can have up to {MAX_PER_BOT} saved replies")
    row = BotSavedReply(bot_id=bot.id, title=payload.title.strip(), body=payload.body.strip(), created_by_user_id=user.id)
    db.add(row)
    db.commit()
    return _read(row)


@router.patch("/{reply_id}")
def update_reply(reply_id: uuid.UUID, payload: SavedReplyPatch, bot: EditableBot, db: DbSession):
    row = _get(db, bot, reply_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(row, field, value.strip())
    db.commit()
    db.refresh(row)
    return _read(row)


@router.delete("/{reply_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reply(reply_id: uuid.UUID, bot: EditableBot, db: DbSession) -> None:
    db.delete(_get(db, bot, reply_id))
    db.commit()
