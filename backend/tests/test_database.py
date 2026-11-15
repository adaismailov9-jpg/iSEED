"""How the store is opened and how it behaves under load and when the database is down."""
import sqlite3
import threading

import pytest
from fastapi.testclient import TestClient

from iseed import main, storage

# ---------------------------------------------------------------- open_store(): which store, which file


@pytest.fixture
def no_env(monkeypatch):
    """No DATABASE_URL / ISEED_DB / VERCEL, and backend/.env cannot bring them back."""
    for key in ("DATABASE_URL", "ISEED_DB", "VERCEL"):
        monkeypatch.setenv(key, "")
    monkeypatch.delenv("VERCEL")
    return monkeypatch


def opened(monkeypatch):
    """Call open_store() and return what it would open, without touching the disk or the network."""
    seen = {}
    monkeypatch.setattr(storage, "SQLiteStore", lambda path: seen.setdefault("sqlite", path))
    from iseed import pgstore
    monkeypatch.setattr(pgstore, "PostgresStore", lambda url: seen.setdefault("postgres", url))
    storage.open_store()
    return seen


def test_local_without_database_url_uses_backend_iseed_db(no_env):
    assert opened(no_env)["sqlite"].replace("\\", "/").endswith("backend/iseed.db")


def test_vercel_without_database_url_uses_tmp(no_env):
    """Vercel's code folder is read-only: SQLite must go to /tmp (this was dead code after a merge)."""
    no_env.setenv("VERCEL", "1")
    assert opened(no_env) == {"sqlite": "/tmp/iseed.db"}


def test_iseed_db_wins_over_the_default(no_env, tmp_path):
    no_env.setenv("VERCEL", "1")
    no_env.setenv("ISEED_DB", str(tmp_path / "mine.db"))
    assert opened(no_env) == {"sqlite": str(tmp_path / "mine.db")}


def test_database_url_means_postgres_even_on_vercel(no_env):
    no_env.setenv("VERCEL", "1")
    no_env.setenv("DATABASE_URL", "postgresql://u:p@ep-x-pooler.neon.tech/db?sslmode=require")
    assert opened(no_env) == {"postgres": "postgresql://u:p@ep-x-pooler.neon.tech/db?sslmode=require"}


def test_engine_settings(monkeypatch):
    """Vercel: no pool, no server-side prepared statements (Neon's pooler); everywhere: a connect timeout."""
    from sqlalchemy.pool import NullPool, QueuePool

    from iseed.pgstore import CONNECT_TIMEOUT_S, make_engine
    captured = []
    import iseed.pgstore as pg
    monkeypatch.setattr(pg, "create_engine", lambda url, **kw: captured.append(kw))
    monkeypatch.setenv("VERCEL", "1")
    make_engine("postgresql://u:p@h/db")
    monkeypatch.delenv("VERCEL")
    make_engine("postgresql://u:p@h/db")
    vercel, local = captured
    assert vercel["poolclass"] is NullPool
    assert vercel["connect_args"] == {"connect_timeout": CONNECT_TIMEOUT_S, "prepare_threshold": None}
    assert local["connect_args"] == {"connect_timeout": CONNECT_TIMEOUT_S} and "poolclass" not in local
    assert QueuePool  # local keeps the default pool


# ---------------------------------------------------------------- parallel requests (both stores)


def test_parallel_use_keeps_every_answer_right(store):
    """FastAPI serves requests on several threads at once; each must get its own, correct answers.
    Without the lock in SQLiteStore, about half of these rounds failed or returned another user's data."""
    errors = []

    def worker(n):
        try:
            for i in range(15):
                user = store.create_user(f"u{n}-{i}", "farmer", "Talas", "V", "1234")
                token = store.create_session(user["id"])
                field_id = store.save_field(user["id"], {"areaHa": n + i / 100})
                assert store.user_for_token(token)["id"] == user["id"]
                assert [f["id"] for f in store.fields_of(user["id"])] == [field_id]
        except Exception as err:  # noqa: BLE001 - collect everything, report below
            errors.append(repr(err))

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []


# ---------------------------------------------------------------- the database is down


def code_of(res):
    return res.status_code, res.json()["code"]


def test_unreachable_postgres_is_a_quick_503(monkeypatch):
    import iseed.pgstore as pg
    monkeypatch.setattr(pg, "CONNECT_TIMEOUT_S", 1)
    monkeypatch.delenv("VERCEL", raising=False)
    down = pg.PostgresStore("postgresql://iseed:x@127.0.0.1:5999/iseed")  # nothing listens there
    monkeypatch.setattr(main, "store", lambda: down)
    api = TestClient(main.app, raise_server_exceptions=False)
    assert code_of(api.post("/login", json={"name": "Aibek", "pin": "1234"})) == (503, "db_unavailable")
    assert api.get("/health").status_code == 200  # routes without the database keep working


def test_unopenable_sqlite_file_is_a_503(monkeypatch, tmp_path):
    def broken():
        return storage.SQLiteStore(str(tmp_path / "no-such-folder" / "iseed.db"))

    monkeypatch.setattr(main, "store", broken)
    api = TestClient(main.app, raise_server_exceptions=False)
    assert code_of(api.post("/login", json={"name": "Aibek", "pin": "1234"})) == (503, "db_unavailable")


def test_sqlite_errors_are_not_all_503(monkeypatch, store):
    """Only 'cannot reach the database' is a 503: a wrong name is still a normal 401."""
    monkeypatch.setattr(main, "store", lambda: store)
    api = TestClient(main.app)
    assert code_of(api.post("/login", json={"name": "Nobody", "pin": "1234"})) == (401, "wrong_login")
    assert sqlite3.OperationalError  # the handled class exists in every Python build
