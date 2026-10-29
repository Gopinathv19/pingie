import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentBot, DbSession, EditableBot
from app.schemas.domain import DomainCreate, DomainRead
from app.services import domain_service

router = APIRouter(prefix="/bots/{bot_id}/domains", tags=["domains"])


@router.get("", response_model=list[DomainRead])
def list_domains(bot: CurrentBot, db: DbSession):
    return [domain_service.to_read(d) for d in domain_service.list_domains(db, bot)]


@router.post("", response_model=DomainRead, status_code=status.HTTP_201_CREATED)
def add_domain(payload: DomainCreate, bot: EditableBot, db: DbSession):
    return domain_service.to_read(domain_service.add_domain(db, bot, payload.host))


@router.delete("/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_domain(domain_id: uuid.UUID, bot: EditableBot, db: DbSession) -> None:
    domain_service.remove_domain(db, bot, domain_id)
