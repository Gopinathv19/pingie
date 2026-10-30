from fastapi import APIRouter, status

from app.api.deps import CurrentBot, DbSession, EditableBot, EditorAccess, Memora, OwnedBot, ViewerAccess
from app.core.config import get_settings
from app.schemas.analytics import Overview
from app.schemas.appearance import WidgetAppearance
from app.schemas.bot import BotDetail, BotUpdate
from app.schemas.domain import InstallInfo
from app.schemas.enums import TimeRange
from app.services import alert_service, analytics_service, bot_service, domain_service

router = APIRouter(prefix="/bots/{bot_id}", tags=["bots"])


@router.get("", response_model=BotDetail)
def get_bot(access: ViewerAccess, db: DbSession):
    return bot_service.to_detail(db, access.bot, access.role, access.via)


@router.patch("", response_model=BotDetail)
def update_bot(payload: BotUpdate, access: EditorAccess, db: DbSession):
    bot_service.update_bot(db, access.bot, payload)
    return bot_service.to_detail(db, access.bot, access.role, access.via)


@router.post("/alerts/test")
def test_alerts(bot: EditableBot):
    """Post a test message to the saved alert URLs now; each URL's HTTP status (or error)."""
    return {"results": alert_service.test(bot)}


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_bot(bot: OwnedBot, db: DbSession, memora: Memora) -> None:
    """Delete the bot, its conversations, and its knowledge in Memora."""
    bot_service.delete_bot(db, bot, memora)


@router.get("/appearance", response_model=WidgetAppearance)
def get_appearance(bot: CurrentBot):
    return bot_service.appearance_of(bot)


@router.put("/appearance", response_model=WidgetAppearance)
def put_appearance(payload: WidgetAppearance, bot: EditableBot, db: DbSession):
    return bot_service.set_appearance(db, bot, payload)


@router.get("/overview", response_model=Overview)
def overview(bot: CurrentBot, db: DbSession, range: TimeRange = "30d"):
    return analytics_service.overview(db, bot, range)


@router.get("/install", response_model=InstallInfo)
def install(bot: CurrentBot, db: DbSession):
    """The embed snippet plus whether the widget has been seen on a domain."""
    script = get_settings().widget_script_url
    seen = [d for d in domain_service.list_domains(db, bot) if d.last_seen_at]
    latest = max(seen, key=lambda d: d.last_seen_at) if seen else None
    return {
        "bot_id": bot.public_id,
        "public_key": bot.public_key,
        "script_url": script,
        "snippet_html": f'<script\n  src="{script}"\n  data-bot-id="{bot.public_id}"\n  defer\n></script>',
        "detected": latest is not None,
        "detected_host": latest.host if latest else None,
        "detected_at": latest.last_seen_at if latest else None,
    }
