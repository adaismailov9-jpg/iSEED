import json

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
            "plan": "beans", "lastCrops": ["beans", "wheat"], "climate": CLIMATE}
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


def test_pump_softens_the_snow_factor():
    assert engine.season_factor("low", "gravity") == 0.75
    assert engine.season_factor("low", "pump") == 0.875
    assert engine.season_factor("low", "well") == 1


def test_manager_turns_and_short_positions():
    view = engine.manager_view("low", "gravity", 6, [{"name": "A", "ha": 100}, {"name": "B", "ha": 150}], "beans", CLIMATE)
    assert view["expectedTurns"] == 4 and not view["enough"]
    assert [p["short"] for p in view["positions"]] == [True, True, True]
    normal = engine.manager_view("normal", "gravity", 6, [{"name": "A", "ha": 250}], "beans", CLIMATE)
    assert normal["expectedTurns"] == 6 and normal["shortM3"] == 0
    assert [p["short"] for p in normal["positions"]] == [False, False, False]


def test_sowing_window_waits_for_frost_and_warm_soil():
    beans = engine.sowing_window(engine.CROPS["beans"], CLIMATE)
    barley = engine.sowing_window(engine.CROPS["barley"], CLIMATE)
    assert beans["earliest"] >= barley["earliest"] >= "05-06"  # day 126 = 6 May
    assert beans["fits"] and engine.sowing_window(engine.CROPS["wheat"], CLIMATE) is None
