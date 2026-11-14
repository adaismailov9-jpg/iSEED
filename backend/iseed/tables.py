"""The PostgresStore tables, as SQLAlchemy Core tables. Alembic builds the migrations from them.

The same five tables as SQLiteStore's SCHEMA, with Postgres types: JSON is JSONB, the message
date is a real DATE, and every row hangs off its user with a foreign key, so deleting a user
deletes their sessions, fields, canal and message.
"""
from sqlalchemy import BigInteger, CheckConstraint, Column, Date, DateTime, ForeignKey, Identity, MetaData, Table, Text, func
from sqlalchemy.dialects.postgresql import JSONB

# Predictable constraint names, so a later migration can find and change them.
metadata = MetaData(naming_convention={
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
})


def _user_fk(**kwargs):
    return Column("user_id", BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, **kwargs)


def _created():
    return Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now())


users = Table(
    "users", metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("name", Text, nullable=False, unique=True),  # the login name
    Column("role", Text, nullable=False),
    Column("region", Text, nullable=False),
    Column("village", Text, nullable=False),
    Column("pin", Text, nullable=False),  # "salt:pbkdf2-sha256 hash", never the PIN itself
    _created(),
    CheckConstraint("role IN ('farmer', 'manager')", name="role"),
)

sessions = Table(
    "sessions", metadata,
    Column("token", Text, primary_key=True),
    _user_fk(index=True),
    _created(),
)

fields = Table(
    "fields", metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    _user_fk(index=True),
    Column("data", JSONB, nullable=False),  # the /fields answer: lat, lon, areaHa, basin, site, geometry...
    _created(),
)

canals = Table(  # one canal per manager
    "canals", metadata,
    _user_fk(primary_key=True),
    Column("data", JSONB, nullable=False),  # villages, source, normalTurns, ...
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

messages = Table(  # one season message per manager, replaced when he posts again
    "messages", metadata,
    _user_fk(primary_key=True),
    Column("text", Text, nullable=False),
    Column("date", Date, nullable=False),
    CheckConstraint("char_length(text) BETWEEN 1 AND 280", name="text_length"),
)
