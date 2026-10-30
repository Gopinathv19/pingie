"""Answers taught from the inbox.

All of a bot's taught answers live in one Memora text source, "Team answers",
rebuilt and re-pushed on every change. One source keeps the plan's source
quota predictable however many answers are added.
"""

import logging
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.clients.memora import MemoraClient
from app.clients.llm import LLMClient
from app.core.errors import NotFoundError, PingError, ValidationError
from app.db.models import Bot, BotAnswer, BotSource, Conversation, Message, Users
from app.reasoning import prompts
from app.services import access_service, bot_service, live_service, source_service

log = logging.getLogger(__name__)

SOURCE_NAME = "Team answers"


def list_answers(db: Session, bot: Bot) -> list[BotAnswer]:
    return list(db.scalars(select(BotAnswer).where(BotAnswer.bot_id == bot.id).order_by(BotAnswer.created_at.desc())))


def _document(answers: list[BotAnswer]) -> str:
    parts = ["# Answers from the support team\n"]
    for a in sorted(answers, key=lambda a: a.created_at):
        prefix = {"summary": "Summary: ", "conversation": "Conversation: "}.get(a.kind, "")
        heading = f"{prefix}{a.question.strip()}"
        parts.append(f"## {heading}\n\n{a.answer.strip()}\n")
    return "\n".join(parts)


def _stage(db: Session, bot: Bot, memora: MemoraClient) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """Push `bot`'s current answers to Memora and point its "Team answers"
    row at the new copy, without committing. Returns (pushed, replaced)
    Memora source ids: the caller commits, then deletes `replaced`."""
    answers = list_answers(db, bot)
    row = db.get(BotSource, bot.faq_source_id) if bot.faq_source_id else None
    if row is not None and row.bot_id != bot.id:
        row = None
    if not answers:
        old_id = row.memora_source_id if row else None
        if row is not None:
            db.delete(row)
        bot.faq_source_id = None
        return None, old_id

    if row is None:
        source_service._assert_source_quota(db, bot)
    text = _document(answers)
    subject_id = bot_service.ensure_subject(db, bot, memora)
    new_id = memora.push_text(subject_id, SOURCE_NAME, text)
    old_id = row.memora_source_id if row else None
    if row is None:
        row = BotSource(bot_id=bot.id, type="text", name=SOURCE_NAME)
        db.add(row)
    row.memora_source_id = new_id
    row.status = "indexing"
    row.progress = 5
    row.error = None
    row.chunk_count = 0
    row.size_bytes = len(text.encode())
    row.last_synced_at = datetime.now(UTC)
    row.last_checked_at = None
    db.flush()
    bot.faq_source_id = row.id
    return new_id, old_id


def _sync(db: Session, bots: list[Bot], memora: MemoraClient) -> None:
    """Commit the pending answer changes only once Memora holds them.

    Saving first and pushing after left answers on screen that Memora never
    received whenever the push failed. Now a failed push rolls the whole
    change back (and removes any copies already pushed for other bots), so
    the dashboard and Memora always agree.
    """
    pushed: list[uuid.UUID] = []
    replaced: list[uuid.UUID] = []
    try:
        for bot in bots:
            new_id, old_id = _stage(db, bot, memora)
            if new_id:
                pushed.append(new_id)
            if old_id:
                replaced.append(old_id)
        db.commit()
    except Exception:
        db.rollback()
        for source_id in pushed:
            _forget(memora, source_id)
        raise
    for source_id in replaced:
        _forget(memora, source_id)


def _forget(memora: MemoraClient, source_id: uuid.UUID) -> None:
    try:
        memora.delete_source(source_id)
    except PingError as exc:
        log.warning("could not delete Memora source %s: %s", source_id, exc.message)


def resync(db: Session, bot: Bot, memora: MemoraClient) -> None:
    """Push the answers again, e.g. ones saved while Memora was unreachable."""
    _sync(db, [bot], memora)


def heal_unsynced(db: Session, memora: MemoraClient) -> int:
    """Bots holding answers that never reached Memora (no "Team answers"
    source, or one whose push failed): push them again. Run at startup."""
    has_answers = select(BotAnswer.bot_id).distinct()
    bots = list(
        db.scalars(
            select(Bot).where(
                Bot.id.in_(has_answers),
                or_(
                    Bot.faq_source_id.is_(None),
                    Bot.faq_source_id.in_(
                        select(BotSource.id).where(or_(BotSource.memora_source_id.is_(None), BotSource.status == "failed"))
                    ),
                ),
            )
        )
    )
    healed = 0
    for bot in bots:
        try:
            resync(db, bot, memora)
            healed += 1
        except PingError as exc:
            log.warning("could not resync team answers of bot %s: %s", bot.id, exc.message)
    return healed


def add_answer(
    db: Session,
    bot: Bot,
    memora: MemoraClient,
    user: Users,
    question: str,
    answer: str,
    conversation_id: uuid.UUID | None = None,
    also_reply: bool = False,
    kind: str = "answer",
    target_bot_ids: list[str] | None = None,
) -> BotAnswer:
    """Save a note on `bot`, and copy it to any other bots of the same workspace.

    Returns the row on `bot`. Every target must be in this bot's workspace and
    editable by the user; one failing target fails the whole call before
    anything is written.
    """
    question, answer = question.strip(), answer.strip()
    if not question or not answer:
        raise ValidationError("Both the question and the answer are needed")
    if kind not in ("answer", "summary", "conversation"):
        raise ValidationError("Unknown note type")
    conv = None
    if conversation_id is not None:
        conv = db.get(Conversation, conversation_id)
        if conv is None or conv.bot_id != bot.id:
            raise NotFoundError("Conversation not found")

    targets = _resolve_targets(db, user, bot, target_bot_ids or [])
    duplicate = _find_duplicate(db, bot, question, answer, kind)
    if duplicate is not None and not targets:
        # Saved twice (a retry after an error, a double click): keep one copy.
        if bot.faq_source_id is None:
            _sync(db, [bot], memora)
        if also_reply and conv is not None:
            live_service.reply(db, conv, user, answer)
        return duplicate
    group = uuid.uuid4() if targets else None
    # ensure_subject commits; do it before any answer row is pending, so
    # nothing is saved unless the push to Memora works.
    for b in (bot, *targets):
        bot_service.ensure_subject(db, b, memora)
    row = BotAnswer(
        bot_id=bot.id, question=question, answer=answer, created_by_user_id=user.id,
        conversation_id=conv.id if conv else None, kind=kind, origin_bot_id=bot.id, share_group_id=group,
    )
    db.add(row)
    for other in targets:
        db.add(
            BotAnswer(
                bot_id=other.id, question=question, answer=answer, created_by_user_id=user.id,
                kind=kind, origin_bot_id=bot.id, share_group_id=group,
            )
        )
    db.flush()
    _sync(db, [bot, *targets], memora)
    if also_reply and conv is not None:
        live_service.reply(db, conv, user, answer)
    return row


def _find_duplicate(db: Session, bot: Bot, question: str, answer: str, kind: str) -> BotAnswer | None:
    return db.scalars(
        select(BotAnswer)
        .where(BotAnswer.bot_id == bot.id, BotAnswer.kind == kind, BotAnswer.question == question, BotAnswer.answer == answer)
        .limit(1)
    ).first()


def _resolve_targets(db: Session, user: Users, bot: Bot, public_ids: list[str]) -> list[Bot]:
    targets: list[Bot] = []
    for public_id in dict.fromkeys(public_ids):
        if public_id == bot.public_id:
            continue
        other = access_service.require_bot_role(db, user, public_id, "editor").bot
        if other.organization_id != bot.organization_id:
            raise ValidationError("Knowledge can only be shared between bots in the same workspace")
        targets.append(other)
    return targets


def draft_from_conversation(
    db: Session, bot: Bot, llm: LLMClient, conversation_id: uuid.UUID, mode: str
) -> list[dict]:
    """Ask the model to turn a conversation into notes. Nothing is saved:
    the person edits the draft first. Personal data is removed by the prompt."""
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.bot_id != bot.id:
        raise NotFoundError("Conversation not found")
    if mode not in ("summary", "qa", "transcript"):
        raise ValidationError("Unknown draft type")
    rows = list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conv.id, Message.role.in_(("visitor", "bot", "agent")))
            .order_by(Message.created_at)
            .limit(60)
        )
    )
    if not rows:
        raise ValidationError("This conversation has no messages to summarise")
    if mode == "transcript":
        return [prompts.scrubbed_transcript(rows)]
    names = {"visitor": "Visitor", "bot": "Bot", "agent": "Team member"}
    transcript = "\n".join(f"{names[m.role]}: {m.content.strip()[:1500]}" for m in rows)
    result = llm.chat(
        [
            {"role": "system", "content": prompts.DRAFT_SYSTEM[mode]},
            {"role": "user", "content": f"Conversation:\n\n{transcript}"},
        ],
        tier="fast",
        max_tokens=900,
        temperature=0.2,
    )
    return prompts.parse_draft(result.content, mode)


def get_answer(db: Session, bot: Bot, answer_id: uuid.UUID) -> BotAnswer:
    row = db.get(BotAnswer, answer_id)
    if row is None or row.bot_id != bot.id:
        raise NotFoundError("Answer not found")
    return row


def delete_answer(db: Session, bot: Bot, memora: MemoraClient, answer_id: uuid.UUID) -> None:
    row = db.get(BotAnswer, answer_id)
    if row is None or row.bot_id != bot.id:
        raise NotFoundError("Answer not found")
    bot_service.ensure_subject(db, bot, memora)
    db.delete(row)
    db.flush()
    _sync(db, [bot], memora)


def update_answer(
    db: Session, bot: Bot, memora: MemoraClient, answer_id: uuid.UUID, question: str, answer: str
) -> BotAnswer:
    """Rewrite one answer on this bot; Memora gets the new text before it is saved."""
    row = db.get(BotAnswer, answer_id)
    if row is None or row.bot_id != bot.id:
        raise NotFoundError("Answer not found")
    question, answer = question.strip(), answer.strip()
    if not question or not answer:
        raise ValidationError("Both the question and the answer are needed")
    if (row.question, row.answer) == (question, answer):
        return row
    bot_service.ensure_subject(db, bot, memora)
    row.question, row.answer = question, answer
    db.flush()
    _sync(db, [bot], memora)
    return row


def share_count(db: Session, rows: list[BotAnswer]) -> dict[uuid.UUID, int]:
    """For each answer, how many other bots hold a copy of it."""
    groups = {r.share_group_id for r in rows if r.share_group_id}
    if not groups:
        return {}
    counts = dict(
        db.execute(
            select(BotAnswer.share_group_id, func.count()).where(BotAnswer.share_group_id.in_(groups)).group_by(BotAnswer.share_group_id)
        ).all()
    )
    return {r.id: counts.get(r.share_group_id, 1) - 1 for r in rows if r.share_group_id}


def to_read(row: BotAnswer, shared_with: int = 0) -> dict:
    return {
        "id": row.id,
        "question": row.question,
        "answer": row.answer,
        "conversation_id": row.conversation_id,
        "created_at": row.created_at,
        "kind": row.kind,
        "origin_bot_id": row.origin_bot_id,
        "shared_with": shared_with,
        "in_help_center": row.in_help_center,
        "helpful": row.helpful_count,
        "unhelpful": row.unhelpful_count,
    }


# --- answering from taught answers --------------------------------------------

_STOP = set(
    "a an the i me my we you your it its is are was be to of in on for and or but so with at by from "
    "this that these those can could would should will do does did have has had any some one need want "
    "please plz pls give get got just like also me how what when where why who which there here".split()
)


def _stem(w: str) -> str:
    """Light stemming so "pricing", "price" and "prices" meet ("pric")."""
    for suffix in ("ing", "ed", "es", "s"):
        if w.endswith(suffix) and not w.endswith("ss") and len(w) - len(suffix) >= 3:
            w = w[: -len(suffix)]
            break
    return w[:-1] if w.endswith("e") and len(w) > 3 else w


def _words(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP and len(w) >= 3}


def taught_match(asked: set[str], taught: set[str]) -> float:
    """How well a visitor's key words match a taught question, 0 to 1.

    Both sides must agree: most of what the visitor asked is in the taught
    question AND most of the taught question is in what they asked. One
    shared word is enough only when each side has a single key word
    ("pricing?" and "What is the price?")."""
    shared = len(asked & taught)
    if not shared:
        return 0.0
    if len(asked) == 1 and len(taught) == 1:
        return 1.0
    if shared < 2:
        return 0.0
    of_asked, of_taught = shared / len(asked), shared / len(taught)
    if of_asked < 0.5 or of_taught < 0.5:
        return 0.0
    return (of_asked + of_taught) / 2


def _squash(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def pick_taught(questions: list[str], rows: list[BotAnswer], passage: str | None = None) -> BotAnswer | None:
    """The taught answer (kind=answer) that best matches the first of
    `questions` that matches any, or None.

    `passage` is the retrieved "Team answers" text; when given, the answer's
    own question must be in it, so the answer sent is the one retrieval found."""
    in_passage = _squash(passage) if passage is not None else None
    candidates = [
        r for r in rows
        if r.kind == "answer" and (in_passage is None or _squash(r.question) in in_passage)
    ]
    for question in questions:
        asked = _words(question)
        if not asked:
            continue
        best, best_score = None, 0.0
        for row in candidates:
            score = taught_match(asked, _words(row.question))
            if score > best_score:
                best, best_score = row, score
        if best is not None:
            return best
    return None


def match_taught_answer(
    db: Session, bot: Bot, questions: list[str], passage: str | None = None, answers: list[BotAnswer] | None = None,
) -> BotAnswer | None:
    """Which taught answer the visitor meant, or None. Only called when
    retrieval already ranked "Team answers" first (see chat_service._taught_reply).
    `answers` stands in for the bot's stored answers when given."""
    return pick_taught(questions, list_answers(db, bot) if answers is None else answers, passage)
