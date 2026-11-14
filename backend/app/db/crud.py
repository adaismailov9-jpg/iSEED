"""Every read and write the API needs, in one place.

Each function takes a Session and does not commit: the caller (session_scope or the
FastAPI dependency) commits once at the end, so a request is all-or-nothing.

Everything that reads user data takes user_id and filters on it, so one user can
never read or change another user's fields or checks.
"""
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .models import Check, Field, PowerCache, User

# ---------------------------------------------------------------- users

PHONE_RE = re.compile(r"^\+[1-9][0-9]{7,14}$")


def normalize_phone(raw: str) -> str:
    """'0555 12-34-56' / '996555123456' / '00996555123456' -> '+996555123456' (E.164)."""
    s = re.sub(r"[\s\-().]", "", raw or "")
    if s.startswith("00"):
        s = "+" + s[2:]
    elif s.startswith("0") and len(s) == 10:  # Kyrgyz local format 0XXX XXX XXX
        s = "+996" + s[1:]
    elif s.startswith("996") and len(s) == 12:
        s = "+" + s
    if not PHONE_RE.match(s):
        raise ValueError(f"not a valid phone number: {raw!r}")
    return s


def get_or_create_user(session: Session, phone: str) -> User:
    """Used after Twilio confirms the code. Safe if two logins for one number race."""
    phone = normalize_phone(phone)
    session.execute(pg_insert(User).values(phone=phone).on_conflict_do_nothing(index_elements=[User.phone]))
    return session.scalars(select(User).where(User.phone == phone)).one()


def get_user(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)


def mark_login(session: Session, user: User) -> None:
    user.last_login_at = datetime.now(timezone.utc)
    session.flush()


def set_user_lang(session: Session, user: User, lang: str) -> None:
    user.lang = lang
    session.flush()


# ---------------------------------------------------------------- fields


def create_field(
    session: Session,
    user_id: int,
    *,
    geometry: dict,
    area_ha: float,
    centroid_lat: float,
    centroid_lon: float,
    basin_id: str | None = None,
    name: str | None = None,
) -> Field:
    field = Field(
        user_id=user_id, geometry=geometry, area_ha=area_ha, centroid_lat=centroid_lat,
        centroid_lon=centroid_lon, basin_id=basin_id, name=name,
    )
    session.add(field)
    session.flush()  # sends the INSERT now, so field.id is known
    return field


def list_fields(session: Session, user_id: int) -> list[Field]:
    stmt = select(Field).where(Field.user_id == user_id).order_by(Field.created_at.desc(), Field.id.desc())
    return list(session.scalars(stmt))


def get_field(session: Session, user_id: int, field_id: int) -> Field | None:
    stmt = select(Field).where(Field.id == field_id, Field.user_id == user_id)
    return session.scalars(stmt).one_or_none()


def rename_field(session: Session, user_id: int, field_id: int, name: str | None) -> Field | None:
    field = get_field(session, user_id, field_id)
    if field is not None:
        field.name = name
        session.flush()
    return field


def delete_field(session: Session, user_id: int, field_id: int) -> bool:
    """Returns False if the field does not exist or belongs to someone else."""
    result = session.execute(delete(Field).where(Field.id == field_id, Field.user_id == user_id))
    return result.rowcount > 0


# ---------------------------------------------------------------- checks (saved verdicts)


def create_check(
    session: Session,
    user_id: int,
    *,
    crop: str,
    water_source: str,
    soil: str,
    season: str,
    snow_year: int,
    snow_level: str,
    verdict: str,
    ratio: float,
    need_m3: int,
    supply_m3: int,
    lang: str,
    result: dict,
    field_id: int | None = None,
    previous_crop: str | None = None,
    requested_crop: str | None = None,
    well_reliability: str | None = None,
    priority: str | None = None,
) -> Check:
    if field_id is not None and get_field(session, user_id, field_id) is None:
        raise LookupError(f"field {field_id} not found for this user")
    check = Check(
        user_id=user_id, field_id=field_id, previous_crop=previous_crop, requested_crop=requested_crop,
        crop=crop, water_source=water_source, well_reliability=well_reliability, soil=soil,
        priority=priority, season=season, snow_year=snow_year, snow_level=snow_level, verdict=verdict,
        ratio=ratio, need_m3=need_m3, supply_m3=supply_m3, lang=lang, result=result,
    )
    session.add(check)
    session.flush()
    return check


def list_checks(session: Session, user_id: int, *, field_id: int | None = None, limit: int = 50) -> list[Check]:
    stmt = select(Check).where(Check.user_id == user_id)
    if field_id is not None:
        stmt = stmt.where(Check.field_id == field_id)
    stmt = stmt.order_by(Check.created_at.desc(), Check.id.desc()).limit(limit)
    return list(session.scalars(stmt))


def get_check(session: Session, user_id: int, check_id: int) -> Check | None:
    stmt = select(Check).where(Check.id == check_id, Check.user_id == user_id)
    return session.scalars(stmt).one_or_none()


# ---------------------------------------------------------------- NASA POWER cache

POWER_CACHE_MAX_AGE = timedelta(days=30)


def power_cell(lat: float, lon: float) -> str:
    """The cache key: the 0.1° cell a point falls in. (+ 0.0 turns -0.0 into 0.0.)"""
    return f"{round(lat, 1) + 0.0:.1f},{round(lon, 1) + 0.0:.1f}"


def get_power_cache(session: Session, cell: str, max_age: timedelta = POWER_CACHE_MAX_AGE) -> dict | None:
    """The cached summary, or None if missing or older than max_age (age is judged by the database clock)."""
    stmt = select(PowerCache.summary).where(
        PowerCache.cell == cell, PowerCache.fetched_at > func.now() - max_age
    )
    return session.execute(stmt).scalar_one_or_none()


def put_power_cache(session: Session, cell: str, summary: dict) -> None:
    """Insert, or replace the old summary and reset fetched_at (an "upsert")."""
    stmt = pg_insert(PowerCache).values(cell=cell, summary=summary)
    stmt = stmt.on_conflict_do_update(
        index_elements=[PowerCache.cell],
        set_={"summary": stmt.excluded.summary, "fetched_at": func.now()},
    )
    session.execute(stmt)


def age_power_cache(session: Session, cell: str, by: timedelta) -> None:
    """Test helper: pretend a cache row was fetched `by` earlier."""
    session.execute(update(PowerCache).where(PowerCache.cell == cell).values(fetched_at=PowerCache.fetched_at - by))
