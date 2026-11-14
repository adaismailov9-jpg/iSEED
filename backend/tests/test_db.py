from datetime import timedelta

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.db import Base, Check, Field, User, crud

SQUARE = {"type": "Polygon", "coordinates": [[[74.6, 42.85], [74.603, 42.85], [74.603, 42.853], [74.6, 42.853], [74.6, 42.85]]]}


def make_field(session, user, **over):
    args = dict(geometry=SQUARE, area_ha=8.2, centroid_lat=42.8515, centroid_lon=74.6015, basin_id="chuy", name="Near the canal")
    args.update(over)
    return crud.create_field(session, user.id, **args)


def make_check(session, user, field=None, **over):
    args = dict(
        crop="barley", water_source="river", soil="medium", season="current", snow_year=2026,
        snow_level="normal", verdict="fits", ratio=1.25, need_m3=36000, supply_m3=45000, lang="ky",
        result={"verdict": {"level": "fits", "sentence": "..."}}, field_id=field.id if field else None,
    )
    args.update(over)
    return crud.create_check(session, user.id, **args)


# ---------------------------------------------------------------- schema


def test_migrations_match_models(engine):
    """If this fails, a model changed without a migration: run `alembic revision --autogenerate`."""
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    assert diff == []


# ---------------------------------------------------------------- users


@pytest.mark.parametrize("raw", ["+996555123456", "0555 123 456", "0555-12-34-56", "996555123456", "00996555123456", "+996 (555) 12 34 56"])
def test_normalize_phone(raw):
    assert crud.normalize_phone(raw) == "+996555123456"


@pytest.mark.parametrize("raw", ["", "123", "555123456", "+0555123456", "+996abc"])
def test_normalize_phone_rejects_junk(raw):
    with pytest.raises(ValueError):
        crud.normalize_phone(raw)


def test_get_or_create_user_is_idempotent(session):
    a = crud.get_or_create_user(session, "0555 123 456")
    b = crud.get_or_create_user(session, "+996555123456")
    assert a.id == b.id
    assert a.lang == "ky"  # server default
    assert session.scalar(select(func.count()).select_from(User)) == 1


def test_database_rejects_bad_phone_even_without_crud(session):
    session.add(User(phone="555"))
    with pytest.raises(IntegrityError, match="ck_users_phone_e164"):
        session.flush()


def test_mark_login_sets_timestamp(session):
    user = crud.get_or_create_user(session, "+996700000001")
    assert user.last_login_at is None
    crud.mark_login(session, user)
    assert user.last_login_at is not None


# ---------------------------------------------------------------- fields


def test_field_round_trip_keeps_geojson(session):
    user = crud.get_or_create_user(session, "+996555000001")
    field = make_field(session, user)
    session.expire_all()  # force a real read from Postgres
    got = crud.get_field(session, user.id, field.id)
    assert got.geometry == SQUARE
    assert got.area_ha == pytest.approx(8.2)


def test_fields_are_private_to_their_owner(session):
    alice = crud.get_or_create_user(session, "+996555000001")
    bob = crud.get_or_create_user(session, "+996555000002")
    field = make_field(session, alice)
    assert crud.get_field(session, bob.id, field.id) is None
    assert crud.list_fields(session, bob.id) == []
    assert crud.delete_field(session, bob.id, field.id) is False
    assert crud.get_field(session, alice.id, field.id) is not None


def test_field_must_be_a_polygon(session):
    user = crud.get_or_create_user(session, "+996555000001")
    with pytest.raises(IntegrityError, match="ck_fields_geometry_polygon"):
        make_field(session, user, geometry={"type": "Point", "coordinates": [74.6, 42.85]})


def test_rename_field(session):
    user = crud.get_or_create_user(session, "+996555000001")
    field = make_field(session, user)
    assert crud.rename_field(session, user.id, field.id, "Upper plot").name == "Upper plot"


# ---------------------------------------------------------------- checks


def test_cannot_save_a_check_on_someone_elses_field(session):
    alice = crud.get_or_create_user(session, "+996555000001")
    bob = crud.get_or_create_user(session, "+996555000002")
    field = make_field(session, alice)
    with pytest.raises(LookupError):
        make_check(session, bob, field)


def test_well_answer_only_for_wells(session):
    user = crud.get_or_create_user(session, "+996555000001")
    make_check(session, user, water_source="well", well_reliability="sometimes")  # ok
    with pytest.raises(IntegrityError, match="ck_checks_well_answer_only_for_wells"):
        make_check(session, user, water_source="river", well_reliability="often")


def test_well_check_needs_a_well_answer(session):
    user = crud.get_or_create_user(session, "+996555000001")
    with pytest.raises(IntegrityError, match="ck_checks_well_answer_only_for_wells"):
        make_check(session, user, water_source="well", well_reliability=None)


def test_unknown_verdict_is_rejected(session):
    user = crud.get_or_create_user(session, "+996555000001")
    with pytest.raises(IntegrityError, match="ck_checks_verdict"):
        make_check(session, user, verdict="maybe")


def test_list_checks_newest_first_and_by_field(session):
    user = crud.get_or_create_user(session, "+996555000001")
    f1, f2 = make_field(session, user), make_field(session, user)
    c1 = make_check(session, user, f1)
    c2 = make_check(session, user, f2)
    c3 = make_check(session, user, f1, crop="chickpea")
    assert [c.id for c in crud.list_checks(session, user.id)] == [c3.id, c2.id, c1.id]
    assert [c.id for c in crud.list_checks(session, user.id, field_id=f1.id)] == [c3.id, c1.id]
    assert len(crud.list_checks(session, user.id, limit=1)) == 1


def test_deleting_a_field_keeps_its_checks(session):
    user = crud.get_or_create_user(session, "+996555000001")
    field = make_field(session, user)
    check = make_check(session, user, field)
    assert crud.delete_field(session, user.id, field.id)
    session.refresh(check)
    assert check.field_id is None  # ON DELETE SET NULL


def test_deleting_a_user_deletes_their_data(session):
    user = crud.get_or_create_user(session, "+996555000001")
    make_check(session, user, make_field(session, user))
    session.execute(delete(User).where(User.id == user.id))  # plain SQL delete: the database cascades
    assert session.scalar(select(func.count()).select_from(Field)) == 0
    assert session.scalar(select(func.count()).select_from(Check)) == 0


# ---------------------------------------------------------------- NASA POWER cache


def test_power_cell_rounding():
    assert crud.power_cell(42.8749, 74.6123) == "42.9,74.6"
    assert crud.power_cell(-0.04, 0.0) == "0.0,0.0"


def test_power_cache_upsert_and_expiry(session):
    cell = crud.power_cell(42.87, 74.61)
    assert crud.get_power_cache(session, cell) is None
    crud.put_power_cache(session, cell, {"frost_free_days": 190})
    assert crud.get_power_cache(session, cell) == {"frost_free_days": 190}
    crud.put_power_cache(session, cell, {"frost_free_days": 200})  # replaces, no duplicate-key error
    assert crud.get_power_cache(session, cell) == {"frost_free_days": 200}
    crud.age_power_cache(session, cell, by=timedelta(days=31))
    assert crud.get_power_cache(session, cell) is None  # older than 30 days counts as missing
