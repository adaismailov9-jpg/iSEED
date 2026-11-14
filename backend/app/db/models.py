"""The four tables: users, fields, checks, power_cache.

Rule of thumb for CHECK constraints: values the engine logic depends on (water source,
soil, snow level, verdict, ...) are locked down in the database. Values that come from
data files and will change during the event (crop ids from crops.csv, basin ids from
basins.geojson, the farmer priority) are plain strings validated by the API instead.
"""
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Identity, Index, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

WATER_SOURCES = ("river", "well", "rain")
WELL_RELIABILITY = ("enough", "sometimes", "often")
SOILS = ("sandy", "medium", "clay", "unknown")
SNOW_LEVELS = ("low", "normal", "high")
VERDICTS = ("fits", "tight", "short")
SEASONS = ("current", "example")  # this year's snow, or the worked example year
LANGS = ("ky", "ru", "en")


def one_of(column: str, values: tuple[str, ...]) -> str:
    """SQL text: column IN ('a', 'b', ...)"""
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


class User(Base):
    """A farmer who logged in with a phone number (Twilio Verify). No password is stored."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    phone: Mapped[str] = mapped_column(String(16), unique=True)  # E.164, e.g. +996555123456
    lang: Mapped[str] = mapped_column(String(2), server_default="ky")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column()

    fields: Mapped[list["Field"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    checks: Mapped[list["Check"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint(r"phone ~ '^\+[1-9][0-9]{7,14}$'", name="phone_e164"),
        CheckConstraint(one_of("lang", LANGS), name="lang"),
    )

    def __repr__(self) -> str:
        return f"User(id={self.id}, phone={self.phone!r})"


class Field(Base):
    """A field the farmer drew on the map. The polygon is kept as GeoJSON in a JSONB column."""

    __tablename__ = "fields"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str | None] = mapped_column(String(80))
    geometry: Mapped[dict]  # {"type": "Polygon", "coordinates": [[[lon, lat], ...]]}
    area_ha: Mapped[float]
    centroid_lat: Mapped[float]
    centroid_lon: Mapped[float]
    basin_id: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    user: Mapped[User] = relationship(back_populates="fields")
    checks: Mapped[list["Check"]] = relationship(back_populates="field", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("area_ha > 0", name="area_positive"),
        CheckConstraint("centroid_lat BETWEEN -90 AND 90", name="lat_range"),
        CheckConstraint("centroid_lon BETWEEN -180 AND 180", name="lon_range"),
        CheckConstraint("geometry ->> 'type' = 'Polygon'", name="geometry_polygon"),
    )

    def __repr__(self) -> str:
        return f"Field(id={self.id}, user_id={self.user_id}, area_ha={self.area_ha})"


class Check(Base):
    """One saved verdict: the farmer's answers, the headline numbers, and the full API response."""

    __tablename__ = "checks"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    # If the field is deleted later, the verdict stays in the history with field_id = NULL.
    field_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("fields.id", ondelete="SET NULL"), index=True
    )

    # The farmer's answers
    previous_crop: Mapped[str | None] = mapped_column(String(32))
    requested_crop: Mapped[str | None] = mapped_column(String(32))  # NULL = "recommend one for me"
    crop: Mapped[str] = mapped_column(String(32))                   # the crop the verdict is about
    water_source: Mapped[str] = mapped_column(String(8))
    well_reliability: Mapped[str | None] = mapped_column(String(10))
    soil: Mapped[str] = mapped_column(String(8))
    priority: Mapped[str | None] = mapped_column(String(16))

    # The answer
    season: Mapped[str] = mapped_column(String(8))
    snow_year: Mapped[int] = mapped_column(SmallInteger)
    snow_level: Mapped[str] = mapped_column(String(8))
    verdict: Mapped[str] = mapped_column(String(8))
    ratio: Mapped[float]
    need_m3: Mapped[int]
    supply_m3: Mapped[int]
    lang: Mapped[str] = mapped_column(String(2))
    result: Mapped[dict]  # the whole /check response, so the screen can reopen it exactly
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped[User] = relationship(back_populates="checks")
    field: Mapped[Field | None] = relationship(back_populates="checks")

    __table_args__ = (
        CheckConstraint(one_of("water_source", WATER_SOURCES), name="water_source"),
        CheckConstraint(one_of("soil", SOILS), name="soil"),
        CheckConstraint(one_of("snow_level", SNOW_LEVELS), name="snow_level"),
        CheckConstraint(one_of("verdict", VERDICTS), name="verdict"),
        CheckConstraint(one_of("season", SEASONS), name="season"),
        CheckConstraint(one_of("lang", LANGS), name="lang"),
        CheckConstraint(
            f"well_reliability IS NULL OR {one_of('well_reliability', WELL_RELIABILITY)}",
            name="well_reliability",
        ),
        # A well answer exists exactly when the water comes from a well.
        CheckConstraint("(water_source = 'well') = (well_reliability IS NOT NULL)", name="well_answer_only_for_wells"),
        CheckConstraint("ratio >= 0 AND need_m3 >= 0 AND supply_m3 >= 0", name="non_negative"),
        # "My last checks, newest first" is the main query.
        Index("ix_checks_user_id_created_at", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"Check(id={self.id}, crop={self.crop!r}, verdict={self.verdict!r})"


class PowerCache(Base):
    """NASA POWER climate summary per 0.1° cell, so each cell is fetched once per 30 days."""

    __tablename__ = "power_cache"

    cell: Mapped[str] = mapped_column(String(16), primary_key=True)  # "42.9,74.6"
    fetched_at: Mapped[datetime] = mapped_column(server_default=func.now())
    summary: Mapped[dict]

    def __repr__(self) -> str:
        return f"PowerCache(cell={self.cell!r}, fetched_at={self.fetched_at})"
