"""Settings read from environment variables (and backend/.env when it exists).

Real environment variables win over .env, so on Vercel the values set in the
project settings are used and no .env file is needed.
"""
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env", override=False)


def normalize_db_url(url: str) -> str:
    """Neon and Heroku hand out postgres:// or postgresql:// URLs; SQLAlchemy needs the driver name."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


@dataclass(frozen=True)
class Settings:
    database_url: str
    test_database_url: str | None
    serverless: bool  # True on Vercel: no connection pool between requests
    sql_echo: bool


@lru_cache
def get_settings() -> Settings:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Run `python scripts/create_local_db.py` "
            "or copy backend/.env.example to backend/.env."
        )
    test_url = os.environ.get("TEST_DATABASE_URL")
    return Settings(
        database_url=normalize_db_url(url),
        test_database_url=normalize_db_url(test_url) if test_url else None,
        serverless=bool(os.environ.get("VERCEL")),
        sql_echo=os.environ.get("SQL_ECHO", "").lower() in ("1", "true", "yes"),
    )
