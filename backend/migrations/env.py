"""Alembic runtime: which database to migrate and which models describe the target schema."""
from logging.config import fileConfig

from alembic import context

from app.config import get_settings
from app.db import models  # noqa: F401  (importing registers the tables on Base.metadata)
from app.db.base import Base
from app.db.session import make_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Autogenerate compares the live database with this metadata.
target_metadata = Base.metadata


def database_url() -> str:
    # Tests pass their own URL (the iseed_test database); otherwise DATABASE_URL.
    return config.attributes.get("database_url") or get_settings().database_url


def _configure(**kwargs) -> None:
    context.configure(target_metadata=target_metadata, compare_type=True, **kwargs)


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL instead of running it."""
    _configure(url=database_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = make_engine(database_url(), serverless=True)  # one short-lived connection
    with engine.connect() as connection:
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
