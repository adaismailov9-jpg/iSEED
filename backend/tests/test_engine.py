import json

import pytest

from iseed import engine

# Talas valley floor, 1,200 m band (NASA POWER 1981-2025), rounded
CLIMATE = {
    "seasonRainMm": 145, "seasonDays": 183, "frostFreeDays": 149,
    "lastSpringFrostDoy": 125, "firstAutumnFrostDoy": 275,
    "weekMeanTempC": [-5] * 12 + [4, 6, 8, 10, 12, 13, 14, 16, 18, 19, 20, 21, 22, 23, 23, 24, 24, 23, 22, 21, 20, 18, 16, 14, 12, 10, 8, 6] + [0] * 12,
    "weekHotDays": [0.0] * 52,
}


def ctx(**over):
    base = {"areaHa": 2.0, "position": "end", "source": "gravity", "normalYear": "enough",
            "plan": "beans", "lastCrops": ["beans", "wheat"], "climate": CLIMATE, "dryAnomaly": -0.5}
    return {**base, **over}


def plan(result):
    return result["options"][0]


def test_well_ignores_snow():
    p = plan(engine.farmer_options(ctx(source="well")))
    assert p["normal"] == p["dry"]


def test_low_snow_hurts_end_of_canal_more_than_start():
    def loss(position):
        p = plan(engine.farmer_options(ctx(position=position)))
        return p["normal"]["income"]["low"] - p["dry"]["income"]["low"]
    assert loss("end") > loss("start") > 0


def test_same_request_gives_same_json():
    assert json.dumps(engine.farmer_options(ctx())) == json.dumps(engine.farmer_options(ctx()))


def test_zero_net_need_does_not_divide_by_zero():
    wet = {**CLIMATE, "seasonRainMm": 5000}
    p = plan(engine.farmer_options(ctx(climate=wet)))
    assert p["netNeedMm"] == 0 and p["dry"]["fit"] == 1


def test_every_crop_and_factor_has_a_source():
    assert all(c["source"] for c in engine.CROPS.values())
    assert all(r["source"] for r in engine.RULES.values())
    assert all(p["source"] and p["date"] for p in engine.PRICES.values())


def test_options_are_never_the_same_crop():
    for crop in engine.CROPS:
        for last in (["beans", "wheat"], ["maize", "maize"], []):
            crops = [o["crop"] for o in engine.farmer_options(ctx(plan=crop, lastCrops=last))["options"]]
            assert len(crops) == len(set(crops)) and crops[0] == crop


def test_water_left_for_the_end_of_the_canal():
    result = engine.farmer_options(ctx(plan="alfalfa"))
    assert plan(result)["waterLeftM3"] == 0
    saver = next(o for o in result["options"] if o["kind"] == "saver")
    assert saver["netNeedMm"] < plan(result)["netNeedMm"] and saver["waterLeftM3"] > 0


def test_soil_builder_avoids_the_last_two_families():
    result = engine.farmer_options(ctx(plan="maize", lastCrops=["wheat", "potato"]))
    builder = next(o for o in result["options"] if o["kind"] == "builder")
    assert engine.CROPS[builder["crop"]]["family"] not in ("cereal", "nightshade")
    assert builder["soil"]["rotation"] == "plus"  # a legume after a cereal


def test_snow_factor_follows_the_anomaly():
    assert engine.season_factor(0, "gravity") == 1
    assert engine.season_factor(-0.2, "gravity") == 0.9
    assert engine.season_factor(-0.5, "gravity") == 0.75  # a typical low-snow year in Talas
    assert engine.season_factor(-1.0, "gravity") == 0.5 and engine.season_factor(0.9, "gravity") == 1.1  # limits
    assert engine.season_factor(-0.5, "pump") == 0.875  # a pump softens it
    assert engine.season_factor(-0.5, "well") == 1


def test_end_of_canal_loses_more_as_the_season_shortens():
    end = [engine.position_factor("end", s, "gravity") for s in (1.1, 1.0, 0.9, 0.75, 0.5)]
    assert end == [0.9, 0.9, pytest.approx(0.78), 0.6, 0.6]
    assert engine.position_factor("start", 0.75, "gravity") == 1 and engine.position_factor("end", 0.75, "well") == 1


def test_manager_turns_and_short_positions():
    villages = [{"name": "A", "ha": 100}, {"name": "B", "ha": 150}]
    dry = engine.manager_view(-0.5, "gravity", 6, villages, "beans", CLIMATE)
    assert dry["expectedTurns"] == 4 and not dry["enough"] and dry["totalHa"] == 250
    assert [p["short"] for p in dry["positions"]] == [True, True, True]
    mild = engine.manager_view(-0.2, "gravity", 6, villages, "beans", CLIMATE)  # Talas, March 2026
    assert mild["expectedTurns"] == 5 and [p["short"] for p in mild["positions"]] == [False, True, True]
    normal = engine.manager_view(0, "gravity", 6, villages, "beans", CLIMATE)
    assert normal["expectedTurns"] == 6 and normal["shortM3"] == 0 and normal["enough"]


def test_sowing_window_waits_for_frost_and_warm_soil():
    beans = engine.sowing_window(engine.CROPS["beans"], CLIMATE)
    barley = engine.sowing_window(engine.CROPS["barley"], CLIMATE)
    assert beans["earliest"] >= barley["earliest"] >= "05-06"  # day 126 = 6 May
    assert beans["fits"] and engine.sowing_window(engine.CROPS["wheat"], CLIMATE) is None
