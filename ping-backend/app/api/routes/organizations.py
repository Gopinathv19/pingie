import uuid

from fastapi import APIRouter, BackgroundTasks, status

from app.api.deps import CurrentUser, DbSession, Memora
from app.schemas.bot import BotCreate, BotDetail, BotSummary
from app.schemas.organization import OrganizationRead, OrganizationUpdate
from app.services import bot_service, organization_service, source_service
from app.services.access_service import require_org_role

router = APIRouter(prefix="/orgs", tags=["organizations"])


@router.get("", response_model=list[OrganizationRead])
def list_orgs(db: DbSession, user: CurrentUser):
    return [organization_service.to_read(db, org, role) for org, role in organization_service.list_for_user(db, user)]


@router.get("/{org_id}", response_model=OrganizationRead)
def get_org(org_id: uuid.UUID, db: DbSession, user: CurrentUser):
    org, role = organization_service.require_member(db, user, org_id)
    return organization_service.to_read(db, org, role)


@router.patch("/{org_id}", response_model=OrganizationRead)
def update_org(org_id: uuid.UUID, payload: OrganizationUpdate, db: DbSession, user: CurrentUser):
    org, role = organization_service.require_member(db, user, org_id)
    require_org_role(role, "owner")
    organization_service.rename(db, org, payload.name)
    return organization_service.to_read(db, org, role)


@router.get("/{org_id}/bots", response_model=list[BotSummary])
def list_bots(org_id: uuid.UUID, db: DbSession, user: CurrentUser):
    org, _ = organization_service.require_member(db, user, org_id)
    return bot_service.list_summaries(db, org)


@router.post("/{org_id}/bots", response_model=BotDetail, status_code=status.HTTP_201_CREATED)
def create_bot(
    org_id: uuid.UUID, payload: BotCreate, background: BackgroundTasks, db: DbSession, user: CurrentUser, memora: Memora
):
    """Create a bot (status `draft`). With `sitemap_url`, crawling starts in
    the background straight away."""
    org, role = organization_service.require_member(db, user, org_id)
    require_org_role(role, "editor")
    bot = bot_service.create_bot(db, org, payload)
    if payload.sitemap_url:
        source = source_service.add_url(db, bot, memora, payload.sitemap_url, "sitemap")
        background.add_task(source_service.process_web_source, source.id)
    return bot_service.to_detail(db, bot, role)
