"""Test fixtures.

The `engine` fixture rebuilds the iseed_test database once per test run by running the
real migrations (upgrade -> downgrade -> upgrade, so the downgrade is tested too).
Each test then runs inside a transaction that is rolled back at the end, so tests
never see each other's rows and the database is left empty.
"""
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR, get_settings
from app.db.session import make_engine


def alembic_config(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.attributes["database_url"] = url
    return cfg


@pytest.fixture(scope="session")
def test_db_url() -> str:
    s = get_settings()
    if not s.test_database_url:
        pytest.skip("TEST_DATABASE_URL is not set (see backend/.env.example)")
    main, test = make_url(s.database_url), make_url(s.test_database_url)
    if (main.host, main.port, main.database) == (test.host, test.port, test.database):
        raise pytest.UsageError("TEST_DATABASE_URL must be a separate database: the tests wipe it")
    return s.test_database_url


@pytest.fixture(scope="session")
def engine(test_db_url):
    cfg = alembic_config(test_db_url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    eng = make_engine(test_db_url)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    with engine.connect() as conn:
        outer = conn.begin()
        # Code under test may call commit(); with savepoints that only ends a savepoint,
        # and the outer transaction is still rolled back below.
        s = Session(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
        try:
            yield s
        finally:
            s.close()
            outer.rollback()
