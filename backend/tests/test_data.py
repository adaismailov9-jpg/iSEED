"""The committed data files agree with each other, with the code and with the frontend.

The API never calls NASA, so a wrong number in data/ is a wrong number on every screen. These checks
recompute what the scripts wrote and compare, and they keep backend and frontend ids in step
(the two once spoke different basin and crop names, and the app only worked on a mock).
"""
import json
import math
from pathlib import Path

import pytest

from iseed import engine
from iseed.climate import DATA, load

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src" / "i18n"


def frontend(lang="en"):
    return json.loads((FRONTEND / f"{lang}.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- ids agree everywhere

def test_basin_ids_are_the_same_in_every_file_and_in_the_frontend():
    geo = {f["properties"]["id"] for f in load("basins.geojson")["features"]}
    ids = {"snow.json": set(load("snow.json")["basins"]), "snow_check.json": set(load("snow_check.json")["basins"]),
           "frontend en": set(frontend()["basins"])}
    for name, found in ids.items():
        assert found == geo, (name, sorted(found ^ geo))


@pytest.mark.parametrize("lang", ["en", "ru", "ky"])
def test_every_crop_has_a_name_in_every_language(lang):
    names = set(frontend(lang)["crops"]) - {"none"}
    assert names == set(engine.CROPS), sorted(names ^ set(engine.CROPS))


def test_prices_are_for_known_crops_and_make_sense():
    assert set(engine.PRICES) <= set(engine.CROPS)
    for crop, p in engine.PRICES.items():
        assert p["source"] and p["date"], crop
        for key in ("yield_t_ha", "price_som_kg"):
            low, high = p[key]
            assert 0 < low <= high, (crop, key)


# ---------------------------------------------------------------- snow.json is what snow_job.py says it is

@pytest.mark.parametrize("basin", sorted(load("snow.json")["basins"]))
def test_snow_numbers_follow_from_the_series(basin):
    b = load("snow.json")["basins"][basin]
    year = int(b["month"][:4])
    series = {p["year"]: p for p in b["series"]}
    assert sorted(series) == list(range(2001, year + 1)) and series[year]["volumeKm3"] == b["volumeKm3"]
    past = [series[y]["volumeKm3"] for y in range(2001, year)]
    normal = sum(past) / len(past)
    # the series is rounded to 0.001 km3 in the file, the normal and the anomaly were made from unrounded values
    assert b["normalKm3"] == pytest.approx(normal, abs=0.002)
    assert b["anomaly"] == pytest.approx((b["volumeKm3"] - normal) / normal, abs=0.005)
    low, high = b["terciles"]
    assert low <= high
    for p in b["series"]:  # the level label of every year follows the terciles
        want = "low" if p["volumeKm3"] < low else "high" if p["volumeKm3"] > high else "normal"
        assert p["level"] == want, (basin, p["year"])
    assert b["level"] == series[year]["level"]
    assert all(p["volumeKm3"] >= 0 and p["wholeBasinKm3"] >= p["volumeKm3"] - 1e-6 for p in b["series"])  # land above 2,000 m is part of the whole basin


def test_every_basin_has_low_years_to_price_the_dry_scenario():
    """dry_year() averages the basin's low years; without any it silently falls back to -50%."""
    for basin, b in load("snow.json")["basins"].items():
        assert any(p["level"] == "low" and p["year"] < 2026 for p in b["series"]), basin


# ---------------------------------------------------------------- climate, rain and grid files have the shape the engine reads

def test_climate_cells_have_complete_weekly_series():
    data = load("climate.json")
    assert data["cells"]
    for cell in data["cells"]:
        assert cell["bands"], cell["lat"]
        for band in cell["bands"]:
            for key in ("weekMeanTempC", "weekHotDays", "weekEt0MmDay"):
                assert len(band[key]) == 52, (cell["lat"], cell["lon"], key)
            assert 0 < band["lastSpringFrostDoy"] < band["firstAutumnFrostDoy"] <= 366
            assert 0 < band["frostFreeDays"] <= 366 and len(band["lastSpringFrostByYear"]) == 45
        assert len(cell["weekRainMm"]) == 52 and all(x >= 0 for x in cell["weekRainMm"])


def test_rain_cells_have_shares_between_0_and_1():
    for cell in load("rain_weeks.json")["cells"]:
        assert len(cell["weekHeavyShare"]) == 52 and all(0 <= s <= 1 for s in cell["weekHeavyShare"])


def test_grid_files_are_as_big_as_the_header_says():
    m = json.loads((DATA / "grid" / "grid.json").read_text())
    cells = m["rows"] * m["cols"]
    for name, size in (("elev.i16", 2), ("slope.u8", 1), ("green.u8", 1), ("bare.u8", 1), ("sand.u8", 1), ("clay.u8", 1)):
        assert (DATA / "grid" / name).stat().st_size == cells * size, name


def test_rules_all_have_a_source_and_a_flag():
    for key, rule in engine.RULES.items():
        assert rule["source"] and isinstance(rule["estimate"], bool) and "value" in rule, key


# ---------------------------------------------------------------- the same place gives sensible numbers anywhere in the country

PLACES = {"talas": (42.52, 72.30), "bishkek": (42.87, 74.59), "karakol": (42.49, 78.39), "naryn": (41.43, 75.99),
          "osh": (40.53, 72.80), "batken": (40.06, 70.82), "jalal-abad": (40.93, 72.98), "kochkor": (42.21, 75.75)}


@pytest.mark.parametrize("place", PLACES)
def test_climate_is_plausible_for_every_region(place):
    from iseed.climate import climate_at
    from iseed.grid import site_at
    lat, lon = PLACES[place]
    c = climate_at(lat, lon, site_at([(lat, lon)])["elevM"])  # the field's own height, as the API does: a POWER cell averages valley and peaks
    assert 60 <= c["frostFreeDays"] <= 260, c["frostFreeDays"]       # FAO AQUASTAT: ~120-140 Naryn, ~185 Chui, ~240 Fergana
    assert 1 <= c["lastSpringFrostDoy"] < c["firstAutumnFrostDoy"] <= 366
    assert -20 < min(c["weekMeanTempC"]) < 5 < max(c["weekMeanTempC"]) < 32
    assert all(math.isfinite(x) and x >= 0 for x in c["weekEt0MmDay"])
