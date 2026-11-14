"""Alembic runtime: which database to migrate (DATABASE_URL) and the target schema (iseed/tables.py)."""
import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv

from iseed.pgstore import make_engine, normalize_url
from iseed.tables import metadata

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = metadata


def database_url() -> str:
    # The tests pass the iseed_test URL; otherwise DATABASE_URL from the environment or backend/.env.
    url = config.attributes.get("database_url") or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set: run `python scripts/create_local_db.py` or set it to the Neon URL")
    return normalize_url(url)


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL instead of running it."""
    context.configure(url=database_url(), target_metadata=target_metadata, literal_binds=True,
                      compare_type=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = make_engine(database_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
