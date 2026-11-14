"""The Store contract: SQLiteStore and PostgresStore must give the same answers.

Tests that take `store` run on both. Tests that take `pg_store` / `pg_engine` check what only
Postgres adds: migrations, constraints and cascades.
"""
from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from iseed import storage, tables

FIELD = {"lat": 42.5205, "lon": 72.3005, "areaHa": 0.91, "basin": "talas", "elevM": 1268,
         "site": None, "fieldCheck": {"verdict": "careful", "checks": [{"id": "slope", "value": 1.5}]},
         "geometry": {"type": "Polygon", "coordinates": [[[72.3, 42.52], [72.301, 42.52], [72.301, 42.521], [72.3, 42.52]]]},
         "note": "Кёк-Сай"}
CANAL = {"villages": [{"name": "Kök-Say", "ha": 120}], "source": "gravity", "normalTurns": 6}


def farmer(store, name="Aibek", village="Kök-Say"):
    return store.create_user(name, "farmer", "Talas", village, "1234")


def manager(store, name="Mirab", village="Talas"):
    return store.create_user(name, "manager", "Talas", village, "1234")


# ---------------------------------------------------------------- users and sessions


def test_create_user_returns_public_fields_only(store):
    user = store.create_user("  Aibek ", "farmer", " Talas", "Kök-Say ", "1234")
    assert user == {"id": 1, "name": "Aibek", "role": "farmer", "region": "Talas", "village": "Kök-Say"}


def test_name_taken_returns_none(store):
    aibek = farmer(store)
    assert store.create_user("Aibek", "manager", "Chüy", "X", "9999") is None
    assert store.check_pin("Aibek", "1234")["role"] == "farmer"  # the first account is untouched
    # Ids only grow. They may skip (Postgres uses up an id on the rejected insert), so never rely on gaps.
    assert farmer(store, name="Bakyt")["id"] > aibek["id"]


def test_check_pin(store):
    user = farmer(store)
    assert store.check_pin(" Aibek", "1234") == user
    assert store.check_pin("Aibek", "0000") is None
    assert store.check_pin("Nobody", "1234") is None


def test_sessions(store):
    user = farmer(store)
    a, b = store.create_session(user["id"]), store.create_session(user["id"])
    assert a != b and len(a) >= 32
    assert store.user_for_token(a) == user == store.user_for_token(b)
    assert store.user_for_token("not-a-token") is None


# ---------------------------------------------------------------- fields


def test_fields_round_trip_in_order_and_per_user(store):
    aibek, bakyt = farmer(store), farmer(store, name="Bakyt")
    first = store.save_field(aibek["id"], FIELD)
    second = store.save_field(aibek["id"], {**FIELD, "areaHa": 2})
    store.save_field(bakyt["id"], FIELD)
    assert [f["id"] for f in store.fields_of(aibek["id"])] == [first, second]
    assert store.fields_of(aibek["id"])[0] == {"id": first, **FIELD}
    assert store.field(first) == {"id": first, "userId": aibek["id"], **FIELD}
    assert store.field(999) is None


# ---------------------------------------------------------------- canal and season message


def test_canal_is_saved_and_replaced(store):
    boss = manager(store)
    assert store.canal_of(boss["id"]) is None
    store.save_canal(boss["id"], CANAL)
    store.save_canal(boss["id"], {**CANAL, "normalTurns": 4})
    assert store.canal_of(boss["id"]) == {**CANAL, "normalTurns": 4}


def test_message_reaches_own_and_canal_villages(store):
    boss = manager(store, village="Talas")
    store.save_canal(boss["id"], CANAL)
    assert store.set_message(boss["id"], "Old text") == {"text": "Old text", "date": date.today().isoformat()}
    store.set_message(boss["id"], "Water turns start 20 April")  # replaces, one message per manager
    expected = {"text": "Water turns start 20 April", "date": date.today().isoformat(), "manager": "Mirab"}
    assert store.message_for(" kök-say ") == expected  # canal village; case and spaces ignored
    assert store.message_for("TALAS") == expected      # the manager's own village
    assert store.message_for("Elsewhere") is None


def test_message_without_canal_uses_own_village(store):
    boss = manager(store, village="Ak-Suu")
    store.set_message(boss["id"], "Hello")
    assert store.message_for("ak-suu")["manager"] == "Mirab"


def test_same_day_newest_manager_wins(store):
    first, second = manager(store, "Mirab"), manager(store, "Asan")
    for boss in (first, second):
        store.save_canal(boss["id"], CANAL)
        store.set_message(boss["id"], f"From {boss['name']}")
    assert store.message_for("Kök-Say")["manager"] == "Asan"  # same date: higher user id first


# ---------------------------------------------------------------- open_store()


def test_open_store_is_sqlite_without_database_url(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "")  # empty, and .env does not override it
    monkeypatch.setenv("ISEED_DB", str(tmp_path / "x.db"))
    assert isinstance(storage.open_store(), storage.SQLiteStore)


def test_open_store_is_postgres_with_database_url(monkeypatch, pg_url):
    from iseed.pgstore import PostgresStore
    monkeypatch.setenv("DATABASE_URL", pg_url)
    store = storage.open_store()
    assert isinstance(store, PostgresStore)
    store.engine.dispose()


def test_neon_style_url_gets_the_driver_name():
    from iseed.pgstore import normalize_url
    assert normalize_url("postgresql://u:p@ep-x.neon.tech/db?sslmode=require") == "postgresql+psycopg://u:p@ep-x.neon.tech/db?sslmode=require"
    assert normalize_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"


# ---------------------------------------------------------------- Postgres only


def test_migrations_match_tables(pg_engine):
    """Fails if tables.py changed without a new migration (`alembic revision --autogenerate`)."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    with pg_engine.connect() as db:
        assert compare_metadata(MigrationContext.configure(db, opts={"compare_type": True}), tables.metadata) == []


def test_pin_is_stored_hashed(pg_store):
    farmer(pg_store)
    with pg_store.engine.connect() as db:
        stored = db.execute(select(tables.users.c.pin)).scalar_one()
    assert "1234" not in stored and storage.pin_matches("1234", stored)


def test_database_rejects_unknown_role(pg_store):
    with pytest.raises(IntegrityError, match="ck_users_role"):
        pg_store.create_user("Aibek", "admin", "Talas", "X", "1234")


def test_database_rejects_long_message(pg_store):
    boss = manager(pg_store)
    with pytest.raises(IntegrityError, match="ck_messages_text_length"):
        pg_store.set_message(boss["id"], "x" * 281)


def test_deleting_a_user_deletes_everything_of_theirs(pg_store):
    boss = manager(pg_store)
    pg_store.create_session(boss["id"])
    pg_store.save_field(boss["id"], FIELD)
    pg_store.save_canal(boss["id"], CANAL)
    pg_store.set_message(boss["id"], "Hello")
    with pg_store.engine.begin() as db:
        db.execute(text("DELETE FROM users"))
        counts = db.execute(text("SELECT (SELECT count(*) FROM sessions) + (SELECT count(*) FROM fields)"
                                 " + (SELECT count(*) FROM canals) + (SELECT count(*) FROM messages)")).scalar_one()
    assert counts == 0


# ---------------------------------------------------------------- session security (both stores)

from datetime import timedelta  # noqa: E402

from conftest import count_rows, stored_session_tokens  # noqa: E402


def test_token_is_stored_only_as_its_hash(store):
    token = store.create_session(farmer(store)["id"])
    assert stored_session_tokens(store) == [storage.token_hash(token)]
    assert token not in stored_session_tokens(store)
    assert store.user_for_token(storage.token_hash(token)) is None  # the stored hash is not a usable token


def test_session_lasts_30_days(store, clock):
    user = farmer(store)
    token = store.create_session(user["id"])
    clock.forward(days=29, hours=23)
    assert store.user_for_token(token) == user
    clock.forward(hours=2)
    assert store.user_for_token(token) is None


def test_expired_sessions_are_cleaned_up(store, clock):
    user = farmer(store)
    store.create_session(user["id"])
    clock.forward(days=31)
    store.create_session(user["id"])
    assert count_rows(store, "sessions") == 1


def test_delete_session_ends_only_that_session(store):
    user = farmer(store)
    phone, laptop = store.create_session(user["id"]), store.create_session(user["id"])
    store.delete_session(phone)
    assert store.user_for_token(phone) is None
    assert store.user_for_token(laptop) == user


def test_failed_logins_are_counted_per_name_and_ip(store, clock):
    since = clock() - timedelta(minutes=15)
    store.add_failed_login("Aibek", "1.1.1.1")
    store.add_failed_login(" Aibek ", "1.1.1.1")
    store.add_failed_login("Bakyt", "1.1.1.1")
    store.add_failed_login("Aibek", "2.2.2.2")
    assert store.failed_logins("Aibek", "1.1.1.1", since) == (3, 3)
    assert store.failed_logins("Bakyt", "2.2.2.2", since) == (1, 1)
    clock.forward(minutes=16)
    assert store.failed_logins("Aibek", "1.1.1.1", clock() - timedelta(minutes=15)) == (0, 0)
    store.clear_failed_logins("Aibek")
    assert store.failed_logins("Aibek", "1.1.1.1", since) == (0, 1)  # only Bakyt's remains on 1.1.1.1


def test_old_failure_records_are_deleted(store, clock):
    store.add_failed_login("Aibek", "1.1.1.1")
    clock.forward(days=2)
    store.add_failed_login("Aibek", "1.1.1.1")
    assert count_rows(store, "login_failures") == 1


def test_old_sqlite_file_with_plain_tokens_is_upgraded(tmp_path):
    import sqlite3
    path = str(tmp_path / "old.db")
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, role TEXT NOT NULL,
          region TEXT NOT NULL, village TEXT NOT NULL, pin TEXT NOT NULL);
        CREATE TABLE sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL);
    """)
    old.execute("INSERT INTO users VALUES (1, 'Aibek', 'farmer', 'Talas', 'Kök-Say', ?)", (storage.hash_pin("1234"),))
    old.execute("INSERT INTO sessions VALUES ('plain-old-token', 1)")
    old.commit()
    old.close()
    store = storage.SQLiteStore(path)
    assert store.user_for_token("plain-old-token") is None  # old plain-text sessions are gone
    assert store.check_pin("Aibek", "1234")["id"] == 1      # accounts are kept
    assert store.user_for_token(store.create_session(1))["name"] == "Aibek"


def test_database_refuses_a_plain_token(pg_store):
    farmer(pg_store)
    with pytest.raises(IntegrityError, match="ck_sessions_token_is_hash"):
        with pg_store.engine.begin() as db:
            db.execute(text("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES ('plain', 1, now())"))


# ---------------------------------------------------------------- update and delete (both stores)


def test_update_user_changes_only_what_is_given(store):
    user = farmer(store)
    updated = store.update_user(user["id"], village=" Ak-Suu ", region="Chüy")
    assert updated == {**user, "village": "Ak-Suu", "region": "Chüy"}
    assert store.update_user(user["id"]) == updated  # nothing given: unchanged


def test_update_user_name_and_pin(store):
    user = farmer(store)
    farmer(store, name="Bakyt")
    assert store.update_user(user["id"], name="Bakyt") is None  # taken
    assert store.update_user(user["id"], name="Aibek K.", pin="9876")["name"] == "Aibek K."
    assert store.check_pin("Aibek K.", "9876")["id"] == user["id"]
    assert store.check_pin("Aibek K.", "1234") is None
    assert store.check_pin("Aibek", "9876") is None


def test_delete_sessions_of_keeps_one(store):
    user = farmer(store)
    a, b, c = (store.create_session(user["id"]) for _ in range(3))
    store.delete_sessions_of(user["id"], keep=b)
    assert [store.user_for_token(x) is not None for x in (a, b, c)] == [False, True, False]
    store.delete_sessions_of(user["id"])
    assert store.user_for_token(b) is None


def test_delete_user_removes_everything_of_theirs_only(store):
    boss, other = manager(store), manager(store, name="Asan", village="Ak-Suu")
    for who in (boss, other):
        store.create_session(who["id"])
        store.save_field(who["id"], FIELD)
        store.save_canal(who["id"], CANAL)
        store.set_message(who["id"], f"From {who['name']}")
    store.delete_user(boss["id"])
    for table, left in (("users", 1), ("sessions", 1), ("fields", 1), ("canals", 1), ("messages", 1)):
        assert count_rows(store, table) == left, table
    assert store.check_pin("Mirab", "1234") is None
    assert store.message_for("Talas") is None              # Mirab's own village: his message is gone
    assert store.message_for("Kök-Say")["manager"] == "Asan"
    assert store.create_user("Mirab", "farmer", "Talas", "X", "1234") is not None  # the name is free again


def test_update_and_delete_field_only_for_its_owner(store):
    aibek, bakyt = farmer(store), farmer(store, name="Bakyt")
    field_id = store.save_field(aibek["id"], FIELD)
    redrawn = {**FIELD, "areaHa": 3.4}
    assert store.update_field(bakyt["id"], field_id, redrawn) is False
    assert store.delete_field(bakyt["id"], field_id) is False
    assert store.field(field_id)["areaHa"] == FIELD["areaHa"]
    assert store.update_field(aibek["id"], field_id, redrawn) is True
    assert store.field(field_id) == {"id": field_id, "userId": aibek["id"], **redrawn}
    assert store.update_field(aibek["id"], 999, redrawn) is False
    assert store.delete_field(aibek["id"], field_id) is True
    assert store.field(field_id) is None and store.fields_of(aibek["id"]) == []
    assert store.delete_field(aibek["id"], field_id) is False


def test_delete_canal_and_message(store):
    boss = manager(store, village="Talas")
    store.save_canal(boss["id"], CANAL)
    store.set_message(boss["id"], "Hello")
    assert store.message_for("Kök-Say")["manager"] == "Mirab"
    assert store.delete_canal(boss["id"]) is True and store.canal_of(boss["id"]) is None
    assert store.message_for("Kök-Say") is None             # canal villages no longer reached
    assert store.message_for("Talas")["text"] == "Hello"    # his own village still is
    assert store.delete_message(boss["id"]) is True and store.message_for("Talas") is None
    assert store.delete_canal(boss["id"]) is False and store.delete_message(boss["id"]) is False
