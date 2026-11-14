"""Shared fixtures for the store tests.

`store` runs each test twice: on SQLiteStore and on PostgresStore. The Postgres run uses the
separate iseed_test database (TEST_DATABASE_URL in backend/.env); it is skipped when that is
not set, so the SQLite run still works on a machine without Docker.
"""
import os
from datetime import timedelta
from pathlib import Path

import pytest

from iseed import storage
from iseed.storage import SQLiteStore

BACKEND = Path(__file__).resolve().parents[1]
TABLES = "users, sessions, fields, canals, messages, login_failures"


def _env_file():
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(BACKEND / ".env", override=False)


@pytest.fixture(scope="session")
def pg_url():
    _env_file()
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set: Postgres tests skipped")
    from sqlalchemy.engine import make_url
    main = os.environ.get("DATABASE_URL")
    if main and make_url(main).database == make_url(url).database:
        raise pytest.UsageError("TEST_DATABASE_URL must be a separate database: the tests wipe it")
    return url


@pytest.fixture(scope="session")
def pg_engine(pg_url):
    """Rebuild iseed_test with the real migrations (upgrade, downgrade, upgrade: both directions are tested)."""
    from alembic import command
    from alembic.config import Config

    from iseed.pgstore import make_engine

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.attributes["database_url"] = pg_url
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = make_engine(pg_url)
    yield engine
    engine.dispose()


@pytest.fixture
def pg_store(pg_engine):
    """An empty PostgresStore; ids restart at 1 like a fresh SQLite file."""
    from sqlalchemy import text

    from iseed.pgstore import PostgresStore

    with pg_engine.begin() as db:
        db.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    return PostgresStore(pg_engine)


@pytest.fixture(params=["sqlite", "postgres"])
def store(request, tmp_path):
    if request.param == "sqlite":
        return SQLiteStore(str(tmp_path / "test.db"))
    return request.getfixturevalue("pg_store")


@pytest.fixture
def clock(monkeypatch):
    """A clock the tests move forward: `clock.forward(days=31)`. Both stores and /login read it."""

    class Clock:
        now = storage.utcnow()

        def __call__(self):
            return self.now

        def forward(self, **kwargs):
            self.now += timedelta(**kwargs)

    fake = Clock()
    monkeypatch.setattr(storage, "utcnow", fake)
    return fake


def stored_session_tokens(store):
    """What the sessions table really holds, read around the store's own methods."""
    if isinstance(store, SQLiteStore):
        return [r[0] for r in store.db.execute("SELECT token_hash FROM sessions")]
    from sqlalchemy import select

    from iseed import tables
    with store.engine.connect() as db:
        return list(db.execute(select(tables.sessions.c.token_hash)).scalars())


def count_rows(store, table):
    if isinstance(store, SQLiteStore):
        return store.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    from sqlalchemy import text
    with store.engine.connect() as db:
        return db.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
