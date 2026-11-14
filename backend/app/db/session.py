"""Engine (the connection pool) and sessions (one unit of work each)."""
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings


def make_engine(url: str, *, serverless: bool = False, echo: bool = False) -> Engine:
    if serverless:
        # A Vercel function may be frozen between requests, so keeping connections open
        # leaks them. Open one per request instead; Neon's pooled URL makes that cheap.
        return create_engine(url, echo=echo, poolclass=NullPool)
    # Long-running server (local uvicorn): keep a few connections open and test them before use.
    return create_engine(url, echo=echo, pool_size=5, max_overflow=5, pool_pre_ping=True)


@lru_cache
def get_engine() -> Engine:
    s = get_settings()
    return make_engine(s.database_url, serverless=s.serverless, echo=s.sql_echo)


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    # expire_on_commit=False: objects stay readable after commit (needed to return them as JSON).
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """`with session_scope() as s:` commits at the end, or rolls back if anything raised."""
    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency: `def route(s: Session = Depends(get_session))` -- one session per request."""
    with session_scope() as session:
        yield session
