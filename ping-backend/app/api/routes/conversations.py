import uuid
from datetime import datetime

from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentBot, CurrentUser, DbSession, EditableBot, Memora, OwnedBot
from app.core.errors import NotFoundError
from app.db.models import Bot, Conversation
from app.schemas.conversation import (
    AgentReply,
    ConversationDetail,
    ConversationPage,
    ConversationUpdates,
    LeadRead,
    MessageRead,
)
from app.schemas.enums import ConversationFilter
from app.services import conversation_service, live_service

router = APIRouter(prefix="/bots/{bot_id}", tags=["conversations"])


@router.get("/conversations", response_model=ConversationPage)
def list_conversations(
    bot: CurrentBot,
    db: DbSession,
    filter: ConversationFilter = "all",
    q: str = "",
    before: datetime | None = None,
):
    """Newest first, 50 per page. Pass `next_before` back as `before`."""
    return conversation_service.list_conversations(db, bot, filter, q, before)


@router.get("/conversations/export.csv")
def export_conversations(bot: CurrentBot, db: DbSession):
    return StreamingResponse(
        conversation_service.export_csv(bot.id),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{bot.public_id}-conversations.csv"'},
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: uuid.UUID, bot: CurrentBot, db: DbSession):
    """The full transcript. Opening it marks the conversation read."""
    return conversation_service.get_conversation(db, bot, conversation_id)


@router.delete("/conversations", status_code=status.HTTP_204_NO_CONTENT)
def clear_history(bot: OwnedBot, db: DbSession, memora: Memora) -> None:
    conversation_service.clear_history(db, bot, memora)


@router.get("/leads", response_model=list[LeadRead])
def list_leads(bot: CurrentBot, db: DbSession):
    return conversation_service.list_leads(db, bot)


# --- Live chat -------------------------------------------------------------------------

def _conversation(db, bot: Bot, conversation_id: uuid.UUID) -> Conversation:
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.bot_id != bot.id:
        raise NotFoundError("Conversation not found")
    return conv


@router.get("/conversations/{conversation_id}/updates", response_model=ConversationUpdates)
def conversation_updates(conversation_id: uuid.UUID, bot: CurrentBot, db: DbSession, after: datetime | None = None):
    """Polled by an open transcript: messages newer than `after` and the status."""
    conv = _conversation(db, bot, conversation_id)
    result = live_service.updates(db, bot, conv, after)
    if result["messages"] and conv.unread:
        conv.unread = False
        db.commit()
    return result


@router.post("/conversations/{conversation_id}/takeover", status_code=status.HTTP_204_NO_CONTENT)
def take_over(conversation_id: uuid.UUID, bot: EditableBot, db: DbSession, user: CurrentUser) -> None:
    live_service.take_over(db, _conversation(db, bot, conversation_id), user)


@router.post("/conversations/{conversation_id}/reply", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
def agent_reply(conversation_id: uuid.UUID, payload: AgentReply, bot: EditableBot, db: DbSession, user: CurrentUser):
    msg = live_service.reply(db, _conversation(db, bot, conversation_id), user, payload.text)
    return live_service.message_to_read(msg, {user.id: (user.name or user.email).split()[0]})


@router.post("/conversations/{conversation_id}/handback", status_code=status.HTTP_204_NO_CONTENT)
def hand_back(conversation_id: uuid.UUID, bot: EditableBot, db: DbSession) -> None:
    live_service.hand_back(db, _conversation(db, bot, conversation_id))


@router.post("/conversations/{conversation_id}/close", status_code=status.HTTP_204_NO_CONTENT)
def close(conversation_id: uuid.UUID, bot: EditableBot, db: DbSession) -> None:
    live_service.close(db, _conversation(db, bot, conversation_id))
