from collections.abc import Iterator

import socket
import time

from sqlalchemy import create_engine, event, exc, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base shared by every model and by Alembic's autogenerate."""


_settings = get_settings()

engine = create_engine(
    _settings.database_url,
    pool_recycle=280,
    future=True,
)

# Neon publishes IPv6 addresses as well as IPv4. On a network with no working
# IPv6 route each IPv6 attempt hangs until it times out, so opening a connection
# took minutes (queries on an open connection took ~40ms). Pin the IPv4 address,
# looked up on every new connection so a DNS change is picked up.
@event.listens_for(engine, "do_connect")
def _prefer_ipv4(dialect, conn_rec, cargs, cparams):
    host = cparams.get("host")
    if not host or cparams.get("hostaddr"):
        return
    try:
        cparams["hostaddr"] = socket.getaddrinfo(host, cparams.get("port") or 5432, socket.AF_INET, socket.SOCK_STREAM)[0][4][0]
    except OSError:
        pass  # no IPv4 record: let the driver resolve it as usual
    cparams.setdefault("connect_timeout", 15)


# Neon closes idle connections, so a pooled one is checked before reuse. Every
# check is a full round trip to the database (hundreds of ms when it is far
# away), so only connections idle for a while are checked, not every request.
_PING_AFTER_IDLE = 20.0


@event.listens_for(engine, "checkout")
def _check_if_idle(dbapi_conn, record, proxy):
    now = time.monotonic()
    last = record.info.get("last_used", 0.0)
    record.info["last_used"] = now
    if now - last < _PING_AFTER_IDLE:
        return
    try:
        cur = dbapi_conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
    except Exception as err:
        raise exc.DisconnectionError() from err

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
