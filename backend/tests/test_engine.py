import json
import math

import pytest

from iseed import engine

# Talas valley floor, 1,200 m band (NASA POWER 1981-2025), rounded
CLIMATE = {
    "seasonRainMm": 145, "seasonDays": 183, "frostFreeDays": 149,
    "lastSpringFrostDoy": 125, "firstAutumnFrostDoy": 275,
    "weekMeanTempC": [-5] * 12 + [4, 6, 8, 10, 12, 13, 14, 16, 18, 19, 20, 21, 22, 23, 23, 24, 24, 23, 22, 21, 20, 18, 16, 14, 12, 10, 8, 6] + [0] * 12,
    "weekHotDays": [0.0] * 52,
}


# The same place with weekly reference evapotranspiration (mm per day) and rain (mm per week)
ET_CLIMATE = {**CLIMATE, "weekEt0MmDay": [0.5] * 12 + [3 + 3 * math.sin(math.pi * i / 27) for i in range(28)] + [0.5] * 12,
              "weekRainMm": [6.0] * 52, "lastSpringFrostByYear": [140 - y // 2 for y in range(45)]}


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
    for wet in ({**CLIMATE, "seasonRainMm": 5000}, {**ET_CLIMATE, "weekRainMm": [500.0] * 52}):
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


def test_water_need_from_evapotranspiration():
    beans = engine.water_need(engine.CROPS["beans"], ET_CLIMATE)
    alfalfa = engine.water_need(engine.CROPS["alfalfa"], ET_CLIMATE)
    assert beans["source"] == "hargreaves" and 250 < beans["grossMm"] < alfalfa["grossMm"] < 1000
    assert beans["netMm"] == pytest.approx(beans["grossMm"] - 0.7 * beans["rainMm"], abs=0.1)
    assert engine.water_need(engine.CROPS["beans"], CLIMATE)["source"] == "typical"  # no ET data: FAO's typical value
    kc = [engine.crop_coefficient(engine.CROPS["beans"], d) for d in (0, 24, 37, 50, 79, 99)]
    assert kc[0] == kc[1] == 0.4 and kc[1] < kc[2] < kc[3] == 1.15 == kc[4] and 0.35 < kc[5] < 1.15


def test_frost_trend_is_said_only_when_significant():
    trend = engine.frost_trend(ET_CLIMATE)  # falls half a day a year
    assert trend["significant"] and trend["daysEarlier"] == 18
    flat = engine.frost_trend({"lastSpringFrostByYear": [120, 131, 118, 127, 122] * 9})
    assert not flat["significant"]


def test_two_crops_only_where_the_season_is_long_enough():
    sown = ctx(climate=ET_CLIMATE, winterWheatSown=True)
    assert engine.farmer_options(sown)["doubleCrop"] is None  # Talas: 84 days after wheat
    south = {**ET_CLIMATE, "firstAutumnFrostDoy": 330, "frostFreeDays": 220}
    double = engine.farmer_options(ctx(climate=south, plan="maize", winterWheatSown=True))["doubleCrop"]
    # warm enough (5 C) from week 13 -> regrowth on day 92, harvest 120 days later on day 212 (31 July)
    assert double["first"] == "wheat" and double["second"] == "beans" and double["wheatHarvest"] == "07-31"
    assert double["windowDays"] == 118


def test_wheat_harvest_stays_inside_june_to_august():
    wheat = engine.CROPS["wheat"]
    for first_warm_week in (4, 13, 29):
        temps = [0] * first_warm_week + [10] * (52 - first_warm_week)
        harvest = engine.wheat_regrowth(wheat, {"weekMeanTempC": temps}) + wheat["days"]
        assert 152 <= harvest <= 243


def test_winter_wheat_is_offered_only_if_already_sown():
    south = {**ET_CLIMATE, "firstAutumnFrostDoy": 310, "frostFreeDays": 220}
    for climate in (CLIMATE, ET_CLIMATE, south):
        result = engine.farmer_options(ctx(climate=climate, plan="maize"))
        assert "wheat" not in [o["crop"] for o in result["options"]] and result["doubleCrop"] is None
    assert engine.farmer_options(ctx(plan="wheat"))["options"][0]["crop"] == "wheat"  # his own plan: already sown
