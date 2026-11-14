"""PostgresStore: the same methods and the same answers as SQLiteStore, kept in PostgreSQL.

Locally Postgres runs in Docker; on Vercel it is Neon. open_store() in storage.py picks this
store when DATABASE_URL is set. Tables are created by the Alembic migrations (backend/migrations),
not here: run `alembic upgrade head` once per database.
"""
import os
import secrets
from datetime import date, timedelta

from sqlalchemy import Engine, create_engine, delete, func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.pool import NullPool

from . import storage
from . import tables as t
from .storage import hash_pin, pin_matches, same_place, token_hash

USER = (t.users.c.id, t.users.c.name, t.users.c.role, t.users.c.region, t.users.c.village)


def normalize_url(url: str) -> str:
    """Neon hands out postgresql://... ; SQLAlchemy needs the driver name: postgresql+psycopg://..."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def make_engine(url: str) -> Engine:
    if os.environ.get("VERCEL"):
        # A serverless function is frozen between requests: open connections would leak.
        # Connect per request instead (use Neon's pooled connection string).
        return create_engine(normalize_url(url), poolclass=NullPool)
    return create_engine(normalize_url(url), pool_size=5, max_overflow=5, pool_pre_ping=True)


class PostgresStore:
    def __init__(self, url_or_engine):
        self.engine = url_or_engine if isinstance(url_or_engine, Engine) else make_engine(url_or_engine)

    # users and sessions
    def create_user(self, name, role, region, village, pin):
        """The new user, or None if the name is taken."""
        stmt = (
            pg_insert(t.users)
            .values(name=name.strip(), role=role, region=region.strip(), village=village.strip(), pin=hash_pin(pin))
            .on_conflict_do_nothing(index_elements=[t.users.c.name])
            .returning(*USER)
        )
        with self.engine.begin() as db:
            row = db.execute(stmt).mappings().first()
        return dict(row) if row else None

    def check_pin(self, name, pin):
        with self.engine.connect() as db:
            row = db.execute(select(*USER, t.users.c.pin).where(t.users.c.name == name.strip())).mappings().first()
        if row and pin_matches(pin, row["pin"]):
            return {c.name: row[c.name] for c in USER}
        return None

    def create_session(self, user_id):
        """A new token. Only its hash is stored; expired sessions are cleaned up on the way."""
        token, now = secrets.token_urlsafe(24), storage.utcnow()
        with self.engine.begin() as db:
            db.execute(delete(t.sessions).where(t.sessions.c.expires_at <= now))
            db.execute(insert(t.sessions).values(token_hash=token_hash(token), user_id=user_id,
                                                 expires_at=now + timedelta(days=storage.SESSION_DAYS)))
        return token

    def user_for_token(self, token):
        """The user of a valid, unexpired session, else None."""
        s = t.sessions
        stmt = (select(*USER).join(s, s.c.user_id == t.users.c.id)
                .where(s.c.token_hash == token_hash(token), s.c.expires_at > storage.utcnow()))
        with self.engine.connect() as db:
            row = db.execute(stmt).mappings().first()
        return dict(row) if row else None

    def delete_session(self, token):
        """Sign out: this token stops working; the user's other sessions stay."""
        with self.engine.begin() as db:
            db.execute(delete(t.sessions).where(t.sessions.c.token_hash == token_hash(token)))

    # wrong-PIN records, for the /login limit
    def failed_logins(self, name, ip, since):
        """(wrong PINs for this name, wrong PINs from this IP) after `since`."""
        f = t.login_failures
        count = lambda col, value: select(func.count()).where(col == value, f.c.at > since).scalar_subquery()  # noqa: E731
        with self.engine.connect() as db:
            row = db.execute(select(count(f.c.name, name.strip()), count(f.c.ip, ip))).one()
        return row[0], row[1]

    def add_failed_login(self, name, ip):
        now, f = storage.utcnow(), t.login_failures
        with self.engine.begin() as db:
            db.execute(delete(f).where(f.c.at <= now - storage.FAILURES_KEPT))
            db.execute(insert(f).values(name=name.strip(), ip=ip, at=now))

    def clear_failed_logins(self, name):
        with self.engine.begin() as db:
            db.execute(delete(t.login_failures).where(t.login_failures.c.name == name.strip()))

    # fields
    def save_field(self, user_id, data):
        with self.engine.begin() as db:
            return db.execute(insert(t.fields).values(user_id=user_id, data=data).returning(t.fields.c.id)).scalar_one()

    def fields_of(self, user_id):
        stmt = select(t.fields.c.id, t.fields.c.data).where(t.fields.c.user_id == user_id).order_by(t.fields.c.id)
        with self.engine.connect() as db:
            return [{"id": r.id, **r.data} for r in db.execute(stmt)]

    def field(self, field_id):
        stmt = select(t.fields.c.id, t.fields.c.user_id, t.fields.c.data).where(t.fields.c.id == field_id)
        with self.engine.connect() as db:
            r = db.execute(stmt).first()
        return r and {"id": r.id, "userId": r.user_id, **r.data}

    # the manager's canal and season message
    def save_canal(self, user_id, data):
        stmt = pg_insert(t.canals).values(user_id=user_id, data=data)
        stmt = stmt.on_conflict_do_update(index_elements=[t.canals.c.user_id],
                                          set_={"data": stmt.excluded.data, "updated_at": func.now()})
        with self.engine.begin() as db:
            db.execute(stmt)

    def canal_of(self, user_id):
        with self.engine.connect() as db:
            return db.execute(select(t.canals.c.data).where(t.canals.c.user_id == user_id)).scalar_one_or_none()

    def set_message(self, user_id, text):
        today = date.today()
        stmt = pg_insert(t.messages).values(user_id=user_id, text=text, date=today)
        stmt = stmt.on_conflict_do_update(index_elements=[t.messages.c.user_id],
                                          set_={"text": stmt.excluded.text, "date": stmt.excluded.date})
        with self.engine.begin() as db:
            db.execute(stmt)
        return {"text": text, "date": today.isoformat()}

    def message_for(self, village):
        """The newest message of a manager whose own village or canal villages include this one."""
        m, u, c = t.messages, t.users, t.canals
        stmt = (
            select(m.c.text, m.c.date, u.c.name, u.c.village, c.c.data)
            .select_from(m.join(u, u.c.id == m.c.user_id).outerjoin(c, c.c.user_id == m.c.user_id))
            .order_by(m.c.date.desc(), m.c.user_id.desc())
        )
        with self.engine.connect() as db:
            rows = db.execute(stmt).all()
        for r in rows:
            villages = [r.village] + [v["name"] for v in (r.data["villages"] if r.data else [])]
            if any(same_place(v, village) for v in villages):
                return {"text": r.text, "date": r.date.isoformat(), "manager": r.name}
        return None
