"""The widget's Help Center: the bot's knowledge as articles a visitor can browse.

Two kinds of article, each addressed as "<kind>:<uuid>":
  page    a web page or small text upload, read from the copy Ping keeps
          (BotSource.content); PDF and DOCX stay answer-only
  answer  a note the team wrote (BotAnswer, kind answer or summary)

Search runs in Ping's own database, so it never waits on Memora.
"""

import re
import uuid

from sqlalchemy import case, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db.models import Bot, BotAnswer, BotSource
from app.services import alert_service

ARTICLE_SOURCE_TYPES = ("page", "url", "text")
ARTICLE_ANSWER_KINDS = ("answer", "summary")
SNIPPET_CHARS = 180


def readable_source():
    """Filters for a source that is listed in the Help Center."""
    return (
        BotSource.type.in_(ARTICLE_SOURCE_TYPES),
        BotSource.status == "ready",
        BotSource.content.is_not(None),
        BotSource.in_help_center.is_(True),
    )


def _listed_answer():
    return (BotAnswer.kind.in_(ARTICLE_ANSWER_KINDS), BotAnswer.in_help_center.is_(True))


def enabled(bot: Bot) -> bool:
    return bool((bot.appearance or {}).get("help_center_enabled", True))


def has_articles(db: Session, bot: Bot) -> bool:
    if not enabled(bot):
        return False
    page = db.scalar(select(BotSource.id).where(BotSource.bot_id == bot.id, *readable_source()).limit(1))
    if page is not None:
        return True
    return db.scalar(select(BotAnswer.id).where(BotAnswer.bot_id == bot.id, *_listed_answer()).limit(1)) is not None


# --- text helpers -------------------------------------------------------------

_MD_NOISE = re.compile(r"!\[[^\]]*\]\([^)]*\)|[#>*_`|~]+")
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")


def plain(markdown: str) -> str:
    text = _MD_LINK.sub(r"\1", markdown or "")
    text = _MD_NOISE.sub(" ", text)
    return " ".join(text.split())


def _without_title(markdown: str, title: str) -> str:
    """Pages are stored as "# Title\\n\\nbody"; the reader shows the title itself."""
    text = (markdown or "").lstrip()
    first, _, rest = text.partition("\n")
    if first.startswith("# ") and first[2:].strip() == title.strip():
        return rest.lstrip()
    return text


def snippet(markdown: str, title: str) -> str:
    text = plain(_without_title(markdown, title))
    return text if len(text) <= SNIPPET_CHARS else text[:SNIPPET_CHARS].rsplit(" ", 1)[0] + "…"


def _page_title(row: BotSource) -> str:
    return row.title or row.name


# --- listing, reading, rating ---------------------------------------------------

def list_articles(db: Session, bot: Bot, q: str = "", limit: int = 20) -> list[dict]:
    if not enabled(bot):
        return []
    q = " ".join((q or "").split())[:200]
    like = f"%{q}%"

    pages = select(BotSource).where(BotSource.bot_id == bot.id, *readable_source())
    answers = select(BotAnswer).where(BotAnswer.bot_id == bot.id, *_listed_answer())
    if q:
        page_title = func.coalesce(func.nullif(BotSource.title, ""), BotSource.name)
        pages = pages.where(or_(page_title.ilike(like), BotSource.content.ilike(like))).order_by(
            case((page_title.ilike(like), 0), else_=1), BotSource.created_at
        )
        answers = answers.where(or_(BotAnswer.question.ilike(like), BotAnswer.answer.ilike(like))).order_by(
            case((BotAnswer.question.ilike(like), 0), else_=1), BotAnswer.created_at.desc()
        )
    else:
        pages = pages.order_by(BotSource.created_at)
        answers = answers.order_by(BotAnswer.created_at.desc())

    items = [
        {
            "id": f"page:{row.id}",
            "title": _page_title(row),
            "snippet": snippet(row.content or "", _page_title(row)),
            "url": row.url,
            "_title_hit": bool(q) and q.lower() in _page_title(row).lower(),
        }
        for row in db.scalars(pages.limit(limit))
    ] + [
        {
            "id": f"answer:{row.id}",
            "title": row.question,
            "snippet": snippet(row.answer, ""),
            "url": None,
            "_title_hit": bool(q) and q.lower() in row.question.lower(),
        }
        for row in db.scalars(answers.limit(limit))
    ]
    # Title matches first; otherwise keep each kind's own order.
    items.sort(key=lambda i: not i["_title_hit"])
    for i in items:
        del i["_title_hit"]
    return items[:limit]


def _resolve(db: Session, bot: Bot, article_id: str) -> BotSource | BotAnswer:
    kind, _, raw = article_id.partition(":")
    try:
        rid = uuid.UUID(raw)
    except ValueError:
        raise NotFoundError("Article not found") from None
    if kind == "page":
        row = db.scalar(select(BotSource).where(BotSource.id == rid, BotSource.bot_id == bot.id, *readable_source()))
    elif kind == "answer":
        row = db.scalar(select(BotAnswer).where(BotAnswer.id == rid, BotAnswer.bot_id == bot.id, *_listed_answer()))
    else:
        row = None
    if row is None or not enabled(bot):
        raise NotFoundError("Article not found")
    return row


def get_article(db: Session, bot: Bot, article_id: str) -> dict:
    row = _resolve(db, bot, article_id)
    if isinstance(row, BotSource):
        title = _page_title(row)
        body = _without_title(row.content or "", title)
        return {"id": article_id, "title": title, "snippet": snippet(body, ""), "url": row.url, "body": body}
    return {"id": article_id, "title": row.question, "snippet": snippet(row.answer, ""), "url": None, "body": row.answer}


def rate_article(db: Session, bot: Bot, article_id: str, helpful: bool) -> None:
    row = _resolve(db, bot, article_id)
    model = type(row)
    column = model.helpful_count if helpful else model.unhelpful_count
    db.execute(update(model).where(model.id == row.id).values({column: column + 1}))
    db.commit()
    if not helpful:
        title = _page_title(row) if isinstance(row, BotSource) else row.question
        alert_service.fire(
            bot, "disliked", visitor="A visitor", text=title,
            headline="A visitor said a Help Center article didn't answer their question",
        )


def most_unhelpful(db: Session, bot: Bot, limit: int = 5) -> list[dict]:
    """For the Overview: the articles visitors said didn't answer their question."""
    pages = db.execute(
        select(BotSource.id, func.coalesce(func.nullif(BotSource.title, ""), BotSource.name), BotSource.helpful_count,
               BotSource.unhelpful_count)
        .where(BotSource.bot_id == bot.id, BotSource.unhelpful_count > 0)
    ).all()
    answers = db.execute(
        select(BotAnswer.id, BotAnswer.question, BotAnswer.helpful_count, BotAnswer.unhelpful_count)
        .where(BotAnswer.bot_id == bot.id, BotAnswer.unhelpful_count > 0)
    ).all()
    rows = [{"id": f"page:{i}", "title": t, "helpful": h, "unhelpful": u} for i, t, h, u in pages]
    rows += [{"id": f"answer:{i}", "title": t, "helpful": h, "unhelpful": u} for i, t, h, u in answers]
    rows.sort(key=lambda r: (-r["unhelpful"], r["helpful"]))
    return rows[:limit]
