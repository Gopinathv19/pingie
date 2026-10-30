import uuid

from fastapi import APIRouter, BackgroundTasks, File, UploadFile, status

from app.api.deps import CurrentBot, DbSession, EditableBot, Memora, ReasonerDep
from app.schemas.source import HelpCenterToggle, SourceList, SourceRead, UrlSourceCreate
from app.schemas.test import TestRequest, TestResponse
from app.services import source_service, test_service

router = APIRouter(prefix="/bots/{bot_id}", tags=["knowledge"])


@router.get("/sources", response_model=SourceList)
def list_sources(bot: CurrentBot, db: DbSession, memora: Memora):
    """Every top-level source, with indexing progress pulled from Memora."""
    return source_service.list_sources(db, bot, memora)


@router.post("/sources/upload", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
def upload(bot: EditableBot, db: DbSession, memora: Memora, file: UploadFile = File(...)):
    content = file.file.read()
    row = source_service.upload_file(db, bot, memora, file.filename or "upload", content, file.content_type)
    return source_service.to_read(row)


@router.post("/sources/url", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
def add_url(payload: UrlSourceCreate, background: BackgroundTasks, bot: EditableBot, db: DbSession, memora: Memora):
    """Add a page or a sitemap. Fetching happens in the background; poll the
    list for progress."""
    row = source_service.add_url(db, bot, memora, payload.url, payload.kind)
    background.add_task(source_service.process_web_source, row.id)
    return source_service.to_read(row)


@router.post("/sources/{source_id}/resync", response_model=SourceRead)
def resync(source_id: uuid.UUID, background: BackgroundTasks, bot: EditableBot, db: DbSession, memora: Memora):
    row = source_service.resync(db, bot, memora, source_id)
    if row.type in ("url", "sitemap"):
        background.add_task(source_service.process_web_source, row.id)
    return source_service.to_read(row)


@router.put("/sources/{source_id}/help-center", response_model=SourceRead)
def help_center(source_id: uuid.UUID, payload: HelpCenterToggle, bot: EditableBot, db: DbSession):
    """Show or hide this source in the widget's Help Center."""
    row = source_service.set_help_center(db, bot, source_id, payload.in_help_center)
    return source_service.to_read(row, source_service._child_help_stats(db, [row.id]).get(row.id))


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(source_id: uuid.UUID, bot: EditableBot, db: DbSession, memora: Memora) -> None:
    source_service.delete_source(db, bot, memora, source_id)


@router.post("/test", response_model=TestResponse)
def test_retrieval(payload: TestRequest, bot: CurrentBot, db: DbSession, reasoner: ReasonerDep):
    """Run retrieval + reasoning for one question without storing anything."""
    return test_service.run_test(db, bot, reasoner, payload.query.strip(), payload.top_k, payload.threshold)
