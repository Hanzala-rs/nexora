import importlib.util
import os
from pathlib import Path

import pytest

# Tests always run against a dedicated database, never DATABASE_URL from .env.
TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:55432/nexora_test")
os.environ.update({
    "DATABASE_URL": TEST_DB,
    "WA_APP_SECRET": "test-app-secret",
    "WA_VERIFY_TOKEN": "test-verify-token",
    "WA_ACCESS_TOKEN": "",
    "WA_PHONE_NUMBER_ID": "",
    "BUSINESS_TIMEZONE": "Asia/Riyadh",
    "BUSINESS_WORKING_DAYS": "sun,mon,tue,wed,thu",
    "BOOKING_DAYS_AHEAD": "7",
})

BACKEND = Path(__file__).resolve().parent.parent


def load_seed():
    """Seed constants from the content migration (single source of truth for content)."""
    spec = importlib.util.spec_from_file_location("seed", BACKEND / "migrations/versions/0002_seed_content.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def content():
    from app.bot.content import build_content
    seed = load_seed()
    return build_content(seed.NODES, seed.TRANSLATIONS, seed.UI_TEXTS)


@pytest.fixture(scope="session")
def migrated_db():
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    from app.db import engine
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError:
        pytest.skip(f"test database not reachable ({TEST_DB.split('@')[-1]})")
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.attributes["configure_logger"] = False
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    return engine


@pytest.fixture
def db(migrated_db):
    from sqlalchemy import text

    from app.db import SessionLocal
    with migrated_db.begin() as conn:
        conn.execute(text("TRUNCATE conversations, messages, consultation_requests, handoff_requests "
                          "RESTART IDENTITY CASCADE"))
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app) as c:
        yield c
