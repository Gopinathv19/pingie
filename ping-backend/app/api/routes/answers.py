"""Answers taught from the inbox ("Teach the bot")."""

import uuid
from typing import Literal

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentBot, CurrentUser, DbSession, EditableBot, LLM, Memora
from app.services import answer_service

router = APIRouter(prefix="/bots/{bot_id}/answers", tags=["answers"])


class AnswerCreate(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    answer: str = Field(min_length=2, max_length=8000)
    conversation_id: uuid.UUID | None = None
    also_reply: bool = False
    kind: Literal["answer", "summary", "conversation"] = "answer"
    # public ids of other bots in this workspace to copy the note to
    target_bot_ids: list[str] = Field(default_factory=list, max_length=50)


class AnswerUpdate(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    answer: str = Field(min_length=2, max_length=8000)


class DraftRequest(BaseModel):
    conversation_id: uuid.UUID
    mode: Literal["summary", "qa", "transcript"]


@router.get("")
def list_answers(bot: CurrentBot, db: DbSession):
    rows = answer_service.list_answers(db, bot)
    shared = answer_service.share_count(db, rows)
    return [answer_service.to_read(a, shared.get(a.id, 0)) for a in rows]


@router.post("/draft")
def draft(payload: DraftRequest, bot: EditableBot, db: DbSession, llm: LLM):
    return {"items": answer_service.draft_from_conversation(db, bot, llm, payload.conversation_id, payload.mode)}


@router.post("", status_code=status.HTTP_201_CREATED)
def add_answer(payload: AnswerCreate, bot: EditableBot, db: DbSession, memora: Memora, user: CurrentUser):
    row = answer_service.add_answer(
        db, bot, memora, user, payload.question, payload.answer, payload.conversation_id, payload.also_reply,
        payload.kind, payload.target_bot_ids,
    )
    return answer_service.to_read(row, len(set(payload.target_bot_ids) - {bot.public_id}))


@router.post("/sync", status_code=status.HTTP_204_NO_CONTENT)
def resync(bot: EditableBot, db: DbSession, memora: Memora) -> None:
    """Push the team answers to Memora again."""
    answer_service.resync(db, bot, memora)


@router.patch("/{answer_id}")
def update_answer(answer_id: uuid.UUID, payload: AnswerUpdate, bot: EditableBot, db: DbSession, memora: Memora):
    row = answer_service.update_answer(db, bot, memora, answer_id, payload.question, payload.answer)
    shared = answer_service.share_count(db, [row])
    return answer_service.to_read(row, shared.get(row.id, 0))


@router.delete("/{answer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_answer(answer_id: uuid.UUID, bot: EditableBot, db: DbSession, memora: Memora) -> None:
    answer_service.delete_answer(db, bot, memora, answer_id)
