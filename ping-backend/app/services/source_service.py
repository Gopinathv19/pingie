"""Knowledge sources: uploads, single pages and sitemaps, indexed by Memora.

Ping owns what the dashboard lists; Memora owns the bytes, the chunks and the
vectors. Files go to Memora as uploads. Web pages are fetched and cleaned by
Ping (Memora has no crawler and keeps HTML tags) and pushed as markdown.

Status flow:  queued (Ping is fetching)  ->  indexing (Memora is extracting,
chunking, embedding)  ->  ready | failed. Memora's progress is pulled lazily
when the list is read, and by a background sweeper.
"""

import logging
import mimetypes
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import PurePath
from urllib.parse import urlparse

from sqlalchemy import case, func, or_, select, update
from sqlalchemy.orm import Session

from app.clients.memora import MemoraClient, get_memora
from app.core.config import get_settings
from app.core.errors import NotFoundError, PingError, QuotaExceededError, ValidationError
from app.db.database import SessionLocal
from app.db.models import Bot, BotSource, Organization
from app.ingestion import crawler
from app.services import bot_service

log = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "text",
    ".md": "text",
    ".markdown": "text",
    ".csv": "text",
}
# Re-ask Memora about an indexing source at most this often.
_REFRESH_INTERVAL = timedelta(seconds=5)
_REFRESH_BATCH = 25


def _now() -> datetime:
    return datetime.now(UTC)


def _display_url(url: str) -> str:
    parsed = urlparse(url)
    return (parsed.netloc + parsed.path).rstrip("/") or url


def source_count(db: Session, bot_id) -> int:
    return db.scalar(
        select(func.count(BotSource.id)).where(BotSource.bot_id == bot_id, BotSource.parent_id.is_(None))
    ) or 0


def _assert_source_quota(db: Session, bot: Bot) -> None:
    org = db.get(Organization, bot.organization_id)
    if org is not None and source_count(db, bot.id) >= org.sources_limit:
        settings = get_settings()
        raise QuotaExceededError(
            f"Your plan allows {org.sources_limit} knowledge sources per bot. "
            f"Email {settings.support_email} to upgrade your plan."
        )


def get_source(db: Session, bot: Bot, source_id: uuid.UUID) -> BotSource:
    row = db.get(BotSource, source_id)
    if row is None or row.bot_id != bot.id or row.parent_id is not None:
        raise NotFoundError("Source not found")
    return row


# --- listing ------------------------------------------------------------------

def list_sources(db: Session, bot: Bot, memora: MemoraClient) -> dict:
    refresh_stale(db, memora, bot_id=bot.id)
    rows = list(
        db.scalars(
            select(BotSource)
            .where(BotSource.bot_id == bot.id, BotSource.parent_id.is_(None))
            .order_by(BotSource.created_at.desc())
        )
    )
    pages = _child_help_stats(db, [r.id for r in rows if r.type == "sitemap"])
    return {"items": [to_read(r, pages.get(r.id)) for r in rows], "summary": _summary(rows)}


def _child_help_stats(db: Session, parent_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int, int]]:
    """Per sitemap: how many crawled pages are readable, and their ratings."""
    if not parent_ids:
        return {}
    rows = db.execute(
        select(
            BotSource.parent_id,
            func.sum(case((BotSource.content.is_not(None), 1), else_=0)),
            func.coalesce(func.sum(BotSource.helpful_count), 0),
            func.coalesce(func.sum(BotSource.unhelpful_count), 0),
        )
        .where(BotSource.parent_id.in_(parent_ids))
        .group_by(BotSource.parent_id)
    ).all()
    return {pid: (int(n or 0), int(h), int(u)) for pid, n, h, u in rows}


def _summary(rows: list[BotSource]) -> dict:
    synced = [r.last_synced_at for r in rows if r.last_synced_at]
    return {
        "total": len(rows),
        "ready": sum(r.status == "ready" for r in rows),
        "failed": sum(r.status == "failed" for r in rows),
        "indexing": sum(r.status in ("queued", "indexing") for r in rows),
        "chunks": sum(r.chunk_count for r in rows if r.status == "ready"),
        "last_sync": max(synced) if synced else None,
    }


def to_read(row: BotSource, pages: tuple[int, int, int] | None = None) -> dict:
    if row.type == "sitemap":
        readable_pages, helpful, unhelpful = pages or (0, 0, 0)
        readable = readable_pages > 0
    else:
        readable = row.content is not None
        helpful, unhelpful = row.helpful_count, row.unhelpful_count
    return {
        # Help Center: whether visitors can read it there, and how they rated it
        "readable": readable,
        "in_help_center": row.in_help_center,
        "helpful": helpful,
        "unhelpful": unhelpful,
        "id": row.id,
        "name": row.name,
        "type": row.type,
        "status": row.status,
        "error": row.error,
        "progress": row.progress,
        "chunks": row.chunk_count,
        "size_bytes": row.size_bytes,
        "page_count": row.page_count,
        "url": row.url,
        "updated_at": row.last_synced_at or row.created_at,
    }


# --- adding -------------------------------------------------------------------

def upload_file(db: Session, bot: Bot, memora: MemoraClient, filename: str, content: bytes, mime: str | None) -> BotSource:
    _assert_source_quota(db, bot)
    settings = get_settings()
    filename = PurePath(filename or "upload").name
    ext = PurePath(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError("Upload a PDF, DOCX, TXT, MD or CSV file")
    if not content:
        raise ValidationError("The file is empty")
    if len(content) > settings.upload_max_bytes:
        raise ValidationError(f"Files must be under {settings.upload_max_bytes // (1024 * 1024)} MB")

    subject_id = bot_service.ensure_subject(db, bot, memora)
    mime = mime or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    memora_id = memora.upload_file(subject_id, filename, content, mime)
    row = BotSource(
        bot_id=bot.id,
        memora_source_id=memora_id,
        type=ALLOWED_EXTENSIONS[ext],
        name=filename,
        status="indexing",
        progress=2,
        size_bytes=len(content),
        last_synced_at=_now(),
    )
    if ext in READABLE_UPLOADS and len(content) <= READABLE_MAX_BYTES:
        _keep_readable(row, PurePath(filename).stem, content.decode("utf-8", errors="replace"))
    db.add(row)
    db.commit()
    return row


# Uploads the Help Center can show as an article; PDF and DOCX stay answer-only.
READABLE_UPLOADS = {".txt", ".md", ".markdown"}
READABLE_MAX_BYTES = 200 * 1024


def _keep_readable(row: BotSource, title: str, markdown: str) -> None:
    """Keep a copy for the widget's Help Center: Memora can't hand a document back."""
    row.title = (title or "").strip()[:300]
    row.content = markdown


def add_url(db: Session, bot: Bot, memora: MemoraClient, url: str, kind: str) -> BotSource:
    """Register a page or sitemap; the fetching runs in the background
    (`process_web_source`), so the request returns immediately."""
    _assert_source_quota(db, bot)
    url = crawler.normalize_url(url)
    if kind == "sitemap" and not urlparse(url).path.strip("/"):
        url = url.rstrip("/") + "/sitemap.xml"
    # Fail fast on Memora config problems instead of in the background.
    bot_service.ensure_subject(db, bot, memora)
    row = BotSource(
        bot_id=bot.id,
        type=kind,
        name=_display_url(url),
        url=url,
        status="queued",
        size_bytes=None,
    )
    db.add(row)
    db.commit()
    return row


# --- background processing ----------------------------------------------------

def process_web_source(source_id: uuid.UUID) -> None:
    """Background task: crawl a page or sitemap and push it to Memora."""
    with SessionLocal() as db:
        row = db.get(BotSource, source_id)
        if row is None:
            return
        bot = db.get(Bot, row.bot_id)
        try:
            if row.type == "url":
                _index_page(db, bot, row, get_memora())
            elif row.type == "sitemap":
                _index_sitemap(db, bot, row, get_memora())
        except (crawler.CrawlError, PingError) as exc:
            row.status = "failed"
            row.error = exc.message if isinstance(exc, PingError) else str(exc)
            db.commit()
        except Exception:  # never let a background task die silently
            log.exception("indexing %s failed", source_id)
            row.status = "failed"
            row.error = "Unexpected error while fetching this source."
            db.commit()


def _index_page(db: Session, bot: Bot, row: BotSource, memora: MemoraClient) -> None:
    fetched = crawler.fetch_page(row.url)
    subject_id = bot_service.ensure_subject(db, bot, memora)
    old = row.memora_source_id
    row.memora_source_id = memora.push_text(subject_id, row.name, fetched.page.markdown)
    row.status = "indexing"
    row.progress = 5
    row.error = None
    row.size_bytes = len(fetched.page.markdown.encode())
    row.page_count = 1
    _keep_readable(row, fetched.page.title, fetched.page.markdown)
    row.last_synced_at = _now()
    db.commit()
    if old:  # a re-sync replaces the previous version
        memora.delete_source(old)


def _index_sitemap(db: Session, bot: Bot, row: BotSource, memora: MemoraClient) -> None:
    settings = get_settings()
    urls = crawler.sitemap_urls(row.url, settings.crawl_max_pages)
    if not urls:
        raise crawler.CrawlError("The sitemap lists no pages")
    subject_id = bot_service.ensure_subject(db, bot, memora)

    children = []
    for url in urls:
        child = BotSource(
            bot_id=bot.id, parent_id=row.id, type="page", name=_display_url(url), url=url, status="queued",
            in_help_center=row.in_help_center,
        )
        db.add(child)
        children.append(child)
    row.status = "indexing"
    row.page_count = len(urls)
    row.progress = 1
    row.error = None
    row.last_synced_at = _now()
    db.commit()
    child_ids = [c.id for c in children]

    def crawl_one(child_id: uuid.UUID) -> None:
        with SessionLocal() as s:
            child = s.get(BotSource, child_id)
            try:
                if not crawler.allowed_by_robots(child.url):
                    raise crawler.CrawlError("Blocked by robots.txt")
                fetched = crawler.fetch_page(child.url)
                child.memora_source_id = memora.push_text(subject_id, child.name, fetched.page.markdown)
                child.status = "indexing"
                child.size_bytes = len(fetched.page.markdown.encode())
                child.last_synced_at = _now()
                _keep_readable(child, fetched.page.title, fetched.page.markdown)
            except (crawler.CrawlError, PingError) as exc:
                child.status = "failed"
                child.error = exc.message if isinstance(exc, PingError) else str(exc)
            s.commit()

    with ThreadPoolExecutor(max_workers=settings.crawl_concurrency) as pool:
        list(pool.map(crawl_one, child_ids))
    _aggregate(db, row)


# --- refreshing from Memora ---------------------------------------------------

def refresh_stale(db: Session, memora: MemoraClient, bot_id: uuid.UUID | None = None) -> int:
    """Ask Memora about sources still indexing, oldest-checked first."""
    cutoff = _now() - _REFRESH_INTERVAL
    query = select(BotSource).where(
        BotSource.status == "indexing",
        BotSource.memora_source_id.is_not(None),
        or_(BotSource.last_checked_at.is_(None), BotSource.last_checked_at < cutoff),
    )
    if bot_id is not None:
        query = query.where(BotSource.bot_id == bot_id)
    rows = list(db.scalars(query.order_by(BotSource.last_checked_at.asc().nulls_first()).limit(_REFRESH_BATCH)))
    if not rows:
        return 0

    def check(row: BotSource):
        age = (_now() - (row.last_synced_at or row.created_at)).total_seconds()
        try:
            return row.id, memora.source_progress(row.memora_source_id, age)
        except PingError as exc:
            log.warning("progress check for %s failed: %s", row.id, exc.message)
            return row.id, None

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(pool.map(check, rows))

    parents: set[uuid.UUID] = set()
    for row in rows:
        row.last_checked_at = _now()
        progress = results.get(row.id)
        if progress is not None:
            row.status = progress.status
            row.chunk_count = progress.chunk_count
            row.progress = progress.progress
            row.error = progress.error
        if row.parent_id:
            parents.add(row.parent_id)
    db.commit()
    for parent_id in parents:
        parent = db.get(BotSource, parent_id)
        if parent is not None:
            _aggregate(db, parent)
    return len(rows)


def _aggregate(db: Session, parent: BotSource) -> None:
    """A sitemap's status and chunk count from its pages."""
    rows = db.execute(
        select(BotSource.status, func.count(BotSource.id), func.coalesce(func.sum(BotSource.chunk_count), 0))
        .where(BotSource.parent_id == parent.id)
        .group_by(BotSource.status)
    ).all()
    by_status = {status: (count, chunks) for status, count, chunks in rows}
    total = sum(c for c, _ in by_status.values())
    ready, ready_chunks = by_status.get("ready", (0, 0))
    failed = by_status.get("failed", (0, 0))[0]
    busy = total - ready - failed
    parent.chunk_count = int(ready_chunks)
    parent.progress = int(100 * (ready + failed) / total) if total else 0
    if busy:
        parent.status = "indexing"
    elif ready:
        parent.status = "ready"
        parent.error = f"{failed} of {total} pages could not be indexed." if failed else None
    else:
        parent.status = "failed"
        parent.error = parent.error or "None of the sitemap's pages could be indexed."
    db.commit()


# --- re-sync and delete -------------------------------------------------------

def resync(db: Session, bot: Bot, memora: MemoraClient, source_id: uuid.UUID) -> BotSource:
    """Files are re-extracted by Memora; pages and sitemaps are re-crawled
    (the caller schedules `process_web_source`)."""
    row = get_source(db, bot, source_id)
    if row.type in ("url", "sitemap"):
        if row.type == "sitemap":
            _delete_children(db, row, memora)
        row.status = "queued"
        row.error = None
        row.progress = 0
        db.commit()
        return row
    if row.memora_source_id is None:
        raise ValidationError("This source has no stored file to re-index; upload it again")
    memora.reextract(row.memora_source_id)
    row.status = "indexing"
    row.error = None
    row.progress = 2
    row.last_synced_at = _now()
    db.commit()
    return row


def set_help_center(db: Session, bot: Bot, source_id: uuid.UUID, on: bool) -> BotSource:
    """List or hide a source in the widget's Help Center (a sitemap's pages follow it)."""
    row = get_source(db, bot, source_id)
    row.in_help_center = on
    if row.type == "sitemap":
        db.execute(update(BotSource).where(BotSource.parent_id == row.id).values(in_help_center=on))
    db.commit()
    return row


def _delete_children(db: Session, row: BotSource, memora: MemoraClient) -> None:
    children = list(db.scalars(select(BotSource).where(BotSource.parent_id == row.id)))
    ids = [c.memora_source_id for c in children if c.memora_source_id]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(memora.delete_source, ids))
    for c in children:
        db.delete(c)
    db.commit()


def delete_source(db: Session, bot: Bot, memora: MemoraClient, source_id: uuid.UUID) -> None:
    row = get_source(db, bot, source_id)
    if row.type == "sitemap":
        _delete_children(db, row, memora)
    if row.memora_source_id:
        memora.delete_source(row.memora_source_id)
    db.delete(row)
    db.commit()


def names_by_memora_id(db: Session, bot_id: uuid.UUID, memora_ids: list[str]) -> dict[str, str]:
    """Ping display names for Memora source ids, for citations."""
    ids = []
    for raw in memora_ids:
        try:
            ids.append(uuid.UUID(raw))
        except (TypeError, ValueError):
            continue
    if not ids:
        return {}
    from app.services import memory_service

    rows = db.execute(
        select(BotSource.memora_source_id, BotSource.name).where(
            BotSource.bot_id == bot_id, BotSource.memora_source_id.in_(ids)
        )
    ).all()
    return {**memory_service.names_by_memora_id(db, bot_id, ids), **{str(mid): name for mid, name in rows}}


def articles_by_memora_id(db: Session, bot_id: uuid.UUID, memora_ids: list[str]) -> dict[str, str]:
    """Help Center article ids for the cited sources that visitors can read."""
    from app.services import help_service

    ids = []
    for raw in memora_ids:
        try:
            ids.append(uuid.UUID(raw))
        except (TypeError, ValueError):
            continue
    if not ids:
        return {}
    rows = db.execute(
        select(BotSource.memora_source_id, BotSource.id).where(
            BotSource.bot_id == bot_id, BotSource.memora_source_id.in_(ids), *help_service.readable_source()
        )
    ).all()
    return {str(mid): f"page:{sid}" for mid, sid in rows}


# --- sweeper ------------------------------------------------------------------

def start_sweeper() -> threading.Thread:
    """Daemon thread that keeps indexing statuses moving even when nobody has
    the Sources page open (analytics and the bot card read them too), and
    pushes finished chats to Memora (chat memory)."""
    interval = get_settings().status_sweeper_interval_seconds

    def loop() -> None:
        while True:
            time.sleep(interval)
            try:
                with SessionLocal() as db:
                    refresh_stale(db, get_memora())
            except Exception:
                log.exception("source status sweep failed")
            try:
                from app.services import memory_service

                with SessionLocal() as db:
                    memory_service.archive_due(db, get_memora())
            except Exception:
                log.exception("chat memory sweep failed")

    thread = threading.Thread(target=loop, name="source-sweeper", daemon=True)
    thread.start()
    return thread


def fail_interrupted(db: Session) -> int:
    """Crawls run in-process; a restart cuts off any still `queued`."""
    rows = list(db.scalars(select(BotSource).where(BotSource.status == "queued")))
    for row in rows:
        row.status = "failed"
        row.error = "Interrupted by a server restart. Re-sync to try again."
    db.commit()
    return len(rows)
