"""Learning from conversations: approve, skip or forget what a bot learned
(app/services/memory_service.py). How much happens on its own is the bot's
`memory_mode`."""

import uuid

from fastapi import APIRouter

from app.api.deps import DbSession, EditableBot, Memora
from app.core.errors import NotFoundError
from app.db.models import Conversation
from app.services import memory_service

router = APIRouter(prefix="/bots/{bot_id}", tags=["memory"])


def _conversation(db, bot, conversation_id: uuid.UUID) -> Conversation:
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.bot_id != bot.id:
        raise NotFoundError("Conversation not found")
    return conv


@router.post("/conversations/{conversation_id}/memory/approve")
def approve(conversation_id: uuid.UUID, bot: EditableBot, db: DbSession, memora: Memora):
    conv = _conversation(db, bot, conversation_id)
    memory_service.approve(db, memora, conv)
    return {"memory_status": conv.memory_status}


@router.post("/conversations/{conversation_id}/memory/skip")
def skip(conversation_id: uuid.UUID, bot: EditableBot, db: DbSession, memora: Memora):
    conv = _conversation(db, bot, conversation_id)
    memory_service.skip(db, memora, conv)
    return {"memory_status": conv.memory_status}


@router.post("/memory/forget")
def forget(bot: EditableBot, db: DbSession, memora: Memora):
    return {"forgotten": memory_service.forget_learned(db, memora, bot)}
