"""The engine's rules, checked over every crop and every situation instead of one example each.

Each test says something that must hold whatever the numbers in rules.json are tuned to, so the team
can change a factor on the day of the hackathon and still know the engine makes sense.
"""
import itertools
import json
import math

import pytest

from iseed import engine
from iseed.climate import climate_at, rain_at

CLIMATE = climate_at(42.52, 72.30, None)
RAIN = rain_at(42.52, 72.30)
ANOMALIES = (-0.9, -0.5, -0.2, 0.0, 0.3)


def ctx(**over):
    base = {"areaHa": 2.0, "position": "end", "source": "gravity", "normalYear": "enough", "plan": "beans",
            "lastCrops": ["beans"], "climate": CLIMATE, "rain": RAIN, "dryAnomaly": -0.5, "winterWheatSown": False}
    return {**base, **over}


def all_situations():
    for plan, position, source, normal in itertools.product(engine.CROPS, engine.POSITIONS, engine.SOURCES, ("enough", "sometimes", "often", "unknown")):
        yield ctx(plan=plan, position=position, source=source, normalYear=normal)


def test_numbers_stay_in_range_in_every_situation():
    for c in all_situations():
        result = engine.farmer_options(c)
        for o in result["options"]:
            for year in ("normal", "dry"):
                y = o[year]
                assert 0 <= y["fit"] <= 1 and 0 <= y["yieldFactor"] <= 1 and y["supplyMm"] >= 0, (c["plan"], o["crop"], year)
                if y["income"]:
                    assert 0 <= y["income"]["low"] <= y["income"]["high"]
            assert o["netNeedMm"] >= 0 and math.isfinite(o["waterLeftM3"])
        json.dumps(result, allow_nan=False)  # no NaN or Infinity in anything the API will send


def test_a_dry_year_never_beats_a_normal_year():
    for c in all_situations():
        for o in engine.farmer_options(c)["options"]:
            assert o["dry"]["fit"] <= o["normal"]["fit"] + 1e-9 and o["dry"]["yieldFactor"] <= o["normal"]["yieldFactor"] + 1e-9


@pytest.mark.parametrize("source", ["gravity", "pump"])
def test_less_snow_never_raises_the_yield(source):
    for plan in engine.CROPS:
        for position in engine.POSITIONS:
            yields = [engine.farmer_options(ctx(plan=plan, position=position, source=source, dryAnomaly=a))["options"][0]["dry"]["yieldFactor"]
                      for a in reversed(ANOMALIES)]  # from a lot of snow down to very little
            assert yields == sorted(yields, reverse=True), (plan, position, yields)


def test_the_end_of_the_canal_never_does_better_than_the_start():
    for plan in engine.CROPS:
        fit = {p: engine.farmer_options(ctx(plan=plan, position=p))["options"][0]["dry"]["fit"] for p in engine.POSITIONS}
        assert fit["start"] >= fit["middle"] >= fit["end"], (plan, fit)


def test_a_well_does_not_care_about_snow():
    for plan in engine.CROPS:
        o = engine.farmer_options(ctx(plan=plan, source="well"))["options"][0]
        assert o["normal"] == o["dry"]


def test_options_start_with_the_plan_and_never_repeat_a_crop_or_a_kind():
    for c in all_situations():
        options = engine.farmer_options(c)["options"]
        assert options[0]["kind"] == "plan" and options[0]["crop"] == c["plan"] and options[0]["waterLeftM3"] == 0
        assert len({o["crop"] for o in options}) == len(options) and len({o["kind"] for o in options}) == len(options)


def test_a_saver_uses_less_water_than_the_plan_and_says_so():
    """Unless the plan is already the least thirsty crop: then the saver is the next thriftiest and shows it takes more."""
    for c in all_situations():
        options = engine.farmer_options(c)["options"]
        saver = next(o for o in options if o["kind"] == "saver")
        if saver["netNeedMm"] < options[0]["netNeedMm"]:
            assert saver["waterLeftM3"] > 0, (c["plan"], saver["crop"])
        else:
            assert saver["waterLeftM3"] <= 0, (c["plan"], saver["crop"])


def test_only_one_option_is_highlighted_and_only_if_it_saves_water():
    for c in all_situations():
        options = engine.farmer_options(c)["options"]
        lit = [o for o in options if o["highlight"]]
        assert len(lit) <= 1 and all(o["waterLeftM3"] > 0 for o in lit)


def test_bigger_field_scales_income_and_water_left_in_proportion():
    small, big = (engine.farmer_options(ctx(areaHa=a, plan="maize")) for a in (1.0, 4.0))
    for s, b in zip(small["options"], big["options"]):
        assert b["waterLeftM3"] == pytest.approx(4 * s["waterLeftM3"], abs=4)  # rounding to whole m3
        if s["normal"]["income"]:
            assert b["normal"]["income"]["low"] == pytest.approx(4 * s["normal"]["income"]["low"], abs=4)


def test_manager_view_is_consistent():
    villages = [{"name": "A", "ha": 100}, {"name": "B", "ha": 50}]
    for anomaly, source in itertools.product(ANOMALIES, ("gravity", "pump")):
        v = engine.manager_view(anomaly, source, 6, villages, "beans", CLIMATE)
        assert 0 <= v["expectedTurns"] <= 6 and v["totalHa"] == 150 and v["shortM3"] >= 0
        assert v["expectedM3"] + v["shortM3"] == pytest.approx(v["demandM3"], abs=2)
        assert v["enough"] == (not any(p["short"] for p in v["positions"]))
        fits = [p["fit"] for p in v["positions"]]
        assert fits == sorted(fits, reverse=True)  # start, middle, end


def test_sowing_window_is_inside_the_frost_free_season():
    for crop in engine.CROPS.values():
        w = engine.sowing_window(crop, CLIMATE)
        if w and w["fits"]:
            assert w["earliest"] <= w["latest"]
