"""Test fixtures.

Like Memora, these run against a real PostgreSQL (JSONB, UUID defaults and
cascades are what ships; SQLite would test something else). Point
TEST_DATABASE_URL at a throwaway database; the schema is built by Alembic.
Tests that need the database are skipped when it is not set.

Memora and VizhiOps are replaced by in-memory fakes (tests/fakes.py) that
speak their HTTP contracts.
"""

import os

import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL")

os.environ["DATABASE_URL"] = TEST_DB or "postgresql+psycopg://unused:unused@localhost:1/unused"
os.environ["AUTH_JWT_SECRET"] = "test-secret-that-is-at-least-32-bytes-long"
os.environ["STATUS_SWEEPER_ENABLED"] = "false"
os.environ["MODEL_PROVIDER"] = "vizhi"
os.environ["VIZHI_TOKEN_BALANCED"] = "vz_live_test"
os.environ["VIZHI_TOKEN_FAST"] = "vz_live_fast"
os.environ["MEMORA_API_TOKEN"] = "memora_test"
os.environ["CRAWL_ALLOW_PRIVATE_HOSTS"] = "false"

TABLES = [
    "bot_answers", "agent_presence", "invitations", "bot_shares", "leads", "messages", "conversations", "visitors", "allowed_domains", "bot_sources",
    "bots", "organization_members", "organizations", "authenticated_user", "users",
]


@pytest.fixture(scope="session")
def database():
    if not TEST_DB:
        pytest.skip("TEST_DATABASE_URL is not set")
    from alembic import command
    from alembic.config import Config

    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "migrations"))
    command.upgrade(cfg, "head")
    return TEST_DB


@pytest.fixture()
def db(database):
    from sqlalchemy import text

    from app.db.database import SessionLocal

    with SessionLocal() as session:
        # A leaked transaction from the previous test would block TRUNCATE
        # forever; fail fast instead.
        session.execute(text("SET lock_timeout = '5s'"))
        session.execute(text(f"TRUNCATE {', '.join(TABLES)} CASCADE"))
        session.commit()
        yield session


@pytest.fixture()
def fakes():
    from app.clients import llm, memora
    from tests.fakes import FakeMemora, FakeVizhi

    m, v = FakeMemora(), FakeVizhi()
    memora.use_memora(m.client())
    llm.use_llm(v.client())
    yield m, v
    memora.use_memora(None)
    llm.use_llm(None)


@pytest.fixture()
def client(db, fakes):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


def sign_in(db, client, email="owner@acme.com", name="Gopi V", sub="google-1"):
    """Sign a user in the way /auth/google does, minus the call to Google."""
    from app.core.config import get_settings
    from app.core.security import create_session_token
    from app.services.auth_service import GoogleIdentity, login_with_identity

    user = login_with_identity(db, GoogleIdentity(sub, email, True, name, ""))
    client.cookies.set(get_settings().auth_cookie_name, create_session_token(user.id, user.email))
    return user


@pytest.fixture()
def owner(db, client):
    return sign_in(db, client)


@pytest.fixture()
def org_id(client, owner):
    return client.get("/api/v1/orgs").json()[0]["id"]


@pytest.fixture()
def bot(client, org_id):
    r = client.post(f"/api/v1/orgs/{org_id}/bots", json={"name": "Acme Help Center", "domain": "https://help.acme.com/"})
    assert r.status_code == 201, r.text
    return r.json()
