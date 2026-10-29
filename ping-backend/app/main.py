import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.api.routes import admin, answers, auth, bots, conversations, domains, live, organizations, plans, sharing, sources, widget
from app.api.widget_cors import WidgetCORSMiddleware
from app.core.config import get_settings
from app.core.errors import NotFoundError, PingError

API_PREFIX = "/api/v1"
# The embeddable widget, built from ping-widget/ (`npm run build:backend`).
WIDGET_SCRIPT = Path(__file__).resolve().parent / "static" / "widget.js"

settings = get_settings()
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Crawls run in this process; any still `queued` were cut off by a restart.
    from app.db.database import SessionLocal
    from app.services import source_service

    try:
        with SessionLocal() as db:
            interrupted = source_service.fail_interrupted(db)
        if interrupted:
            log.warning("marked %d interrupted crawl(s) as failed", interrupted)
    except Exception:
        log.exception("could not check for interrupted crawls")

    # Team answers saved while pushes to Memora were failing never reached it.
    try:
        from app.clients.memora import get_memora
        from app.services import answer_service

        with SessionLocal() as db:
            healed = answer_service.heal_unsynced(db, get_memora())
        if healed:
            log.warning("re-pushed team answers of %d bot(s) to Memora", healed)
    except Exception:
        log.exception("could not re-push team answers")

    if settings.status_sweeper_enabled:
        source_service.start_sweeper()
    yield


api = FastAPI(
    lifespan=lifespan,
    title="Ping",
    version="0.1.0",
    description=(
        "Ping runs AI support bots for websites. Memora retrieves the passages "
        "(retrieval only); Ping reasons over them and writes every answer "
        "through the configured LLM provider (VizhiOps by default)."
    ),
    docs_url="/docs",
)

api.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@api.exception_handler(PingError)
def handle_ping_error(_: Request, exc: PingError) -> JSONResponse:
    """Domain errors become consistent JSON: `detail` is always present."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message, "code": exc.code})


# Tables are created by Alembic only, never by create_all() at boot.
for router in (
    auth.router,
    organizations.router,
    bots.router,
    sources.router,
    domains.router,
    conversations.router,
    widget.router,
    admin.router,
    plans.router,
    sharing.router,
    live.router,
    answers.router,
):
    api.include_router(router, prefix=API_PREFIX)


@api.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@api.get("/widget.js", include_in_schema=False)
def widget_script() -> FileResponse:
    """The widget customers embed with a <script> tag. Served from the API's
    own origin, so the widget calls this same host by default. A plain script
    tag needs no CORS. The short cache lets a redeploy reach every site within
    minutes, since customers never change the snippet."""
    if not WIDGET_SCRIPT.is_file():
        raise NotFoundError("The widget has not been built (run `npm run build:backend` in ping-widget)")
    return FileResponse(WIDGET_SCRIPT, media_type="text/javascript", headers={"Cache-Control": "public, max-age=300"})


# The widget routes answer customers' origins; everything else only the
# dashboard's. The wrapper owns CORS for /api/v1/widget/*.
app = WidgetCORSMiddleware(api)
