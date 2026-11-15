"""The iSEED rules (ТЗ section 4). Deterministic: no AI, no randomness, same input, same answer.

Every number used here comes from data/rules.json, crops.csv or prices.json, where it has a
source and is marked as an estimate if it is one. `climate` is one height band of one NASA
POWER cell (see climate.py); `rain` is the GPM IMERG cell; `site` is the terrain grid (grid.py).
"""
import csv
import json
import math
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).parent / "data"
RULES = json.loads((DATA / "rules.json").read_text(encoding="utf-8"))
PRICES = json.loads((DATA / "prices.json").read_text(encoding="utf-8"))
POSITIONS = ("start", "middle", "end")
SOURCES = ("gravity", "pump", "well")
LEVELS = ("good", "careful", "no")


def _load_crops():
    crops = {}
    with open(DATA / "crops.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            stages = [int(d) for d in r["stage_days"].split("/")]  # initial / development / mid / late
            crops[r["id"]] = {
                "id": r["id"],
                "family": r["family"],
                "fixesN": r["fixes_n"] == "1",
                "winter": r["winter"] == "1",
                "perennial": r["perennial"] == "1",
                "stageDays": stages,
                "kc": [float(k) for k in r["kc"].split("/")],  # initial / mid / end
                "days": sum(stages),
                "needMm": float(r["need_mm"]),  # typical value, used only without evapotranspiration data
                "ky": float(r["ky"]),
                "minSowTempC": float(r["min_sow_temp_c"]) if r["min_sow_temp_c"] else None,
                "daysToFlower": int(r["days_to_flower"]) if r["days_to_flower"] else None,
                "source": r["source"],
            }
    return crops


CROPS = _load_crops()


def rule(key):
    return RULES[key]["value"]


def week_of(doy):
    return min(51, (int(doy) - 1) // 7)


def month_day(doy):
    """Day of year as MM-DD (of a non-leap year)."""
    return (date(2027, 1, 1) + timedelta(days=int(doy) - 1)).strftime("%m-%d")


# --- Step 1. Season water factor S, from the basin's snow anomaly (-0.2 = 20% below normal)

def season_factor(anomaly, source):
    if source == "well":
        return 1.0
    limits = rule("snow_factor_limits")
    s = min(limits["max"], max(limits["min"], 1 + rule("snow_sensitivity") * anomaly))
    if source == "pump":  # a pump on a big river feels a snow deficit less
        s = 1 - rule("pump_softening") * (1 - s)
    return s


# --- Step 2. Canal position factor P: the share of the allocation that reaches the field.
# The end of the canal loses more the shorter the season is.

def position_factor(position, s, source):
    if source == "well":
        return 1.0
    p = rule("position_factor")[position]
    dryness = min(1.0, max(0.0, (1 - s) / (1 - rule("position_low_at"))))
    return p["normal"] + (p["low"] - p["normal"]) * dryness


# --- Step 9 (needed first: the crop's water need depends on when it grows). Sowing window.

def sowing_days(crop, climate):
    """(earliest, latest) day of year to sow, or None for winter crops and crops without a sowing temperature.

    Earliest: after the last spring frost in 9 years out of 10, once the weekly mean temperature
    has reached the crop's minimum. Latest: it still matures before the first autumn frost in 9 of 10.
    """
    temps = climate.get("weekMeanTempC")
    if crop["winter"] or crop["minSowTempC"] is None or not temps:
        return None
    week = week_of(climate["lastSpringFrostDoy"])
    while week < 51 and temps[week] < crop["minSowTempC"]:
        week += 1
    earliest = max(climate["lastSpringFrostDoy"] + 1, week * 7 + 1)
    return earliest, climate["firstAutumnFrostDoy"] - crop["days"]


def sowing_window(crop, climate, rain=None):
    days = sowing_days(crop, climate)
    if not days:
        return None
    earliest, latest = days
    fits = latest >= earliest
    out = {"earliest": month_day(earliest), "latest": month_day(latest) if fits else None, "fits": fits}
    if crop["daysToFlower"]:
        flower = earliest + crop["daysToFlower"]
        hot = climate["weekHotDays"][week_of(flower)]
        out["flowering"] = {"date": month_day(flower), "hotDays": hot, "tooHot": hot >= rule("heat_days_week")}
    if rain:
        # Sowing weeks: from the earliest date, at most `sowing_weeks`, never past the latest date.
        first = week_of(earliest)
        last = min(first + rule("sowing_weeks") - 1, max(first, week_of(max(latest, 1))))
        share = rain["weekHeavyShare"]
        best = min(range(first, last + 1), key=lambda w: (share[w], w))
        out["heavyRain"] = {
            "maxShare": max(share[first:last + 1]),
            "suggested": month_day(max(earliest, best * 7 + 1)),
            "riskyWeeks": [month_day(w * 7 + 1) for w in range(first, last + 1) if share[w] >= rule("heavy_rain_share")["no"]],
        }
    return out


def mann_kendall_p(values):
    """Two-sided p-value of the Mann-Kendall trend test (normal approximation, corrected for ties)."""
    n = len(values)
    s = sum((b > a) - (b < a) for i, a in enumerate(values) for b in values[i + 1:])
    ties = sum(t * (t - 1) * (2 * t + 5) for t in (values.count(v) for v in set(values)))
    var = (n * (n - 1) * (2 * n + 5) - ties) / 18
    if var == 0 or s == 0:
        return 1.0
    z = (s - (1 if s > 0 else -1)) / math.sqrt(var)
    return math.erfc(abs(z) / math.sqrt(2))


def frost_trend(climate):
    """Does the last spring frost come earlier now than in the 1980s? Said only if the trend is significant."""
    by_year = climate.get("lastSpringFrostByYear")  # 1981-2025
    if not by_year:
        return None
    p = mann_kendall_p(by_year)
    first, last = by_year[:10], by_year[-10:]
    return {"significant": p < rule("trend_p"), "p": round(p, 3),
            "daysEarlier": round(sum(first) / len(first) - sum(last) / len(last)),
            "from": "1981-1990", "to": "2016-2025"}


# --- Step 3. Crop water need (mm per season)

def crop_coefficient(crop, day):
    """FAO-56 crop coefficient on a day of the season: flat, rising, flat, falling."""
    ini, dev, mid, late = crop["stageDays"]
    kc_ini, kc_mid, kc_end = crop["kc"]
    if day < ini:
        return kc_ini
    if day < ini + dev:
        return kc_ini + (kc_mid - kc_ini) * (day - ini) / dev
    if day < ini + dev + mid:
        return kc_mid
    return kc_mid + (kc_end - kc_mid) * (day - ini - dev - mid) / late


def wheat_regrowth(crop, climate):
    """Day winter wheat starts growing again in spring: the first week warm enough (NASA POWER),
    placed so that harvest falls inside the June-August window farmers report."""
    temps = climate.get("weekMeanTempC")
    week = next((w for w in range(4, 30) if temps and temps[w] is not None and temps[w] >= rule("wheat_regrowth_c")), 13)
    window = rule("wheat_harvest_window")
    harvest = min(window["to"], max(window["from"], week * 7 + 1 + crop["days"]))
    return harvest - crop["days"]


def season_start(crop, climate):
    """Day of year from which the crop draws irrigation water."""
    if crop["winter"]:
        return wheat_regrowth(crop, climate)
    days = sowing_days(crop, climate)
    return days[0] if days else climate["lastSpringFrostDoy"] + 1


def water_need(crop, climate, start=None):
    """Need = sum over the season of crop coefficient x reference evapotranspiration (Hargreaves, NASA POWER).
    Net need = need - useful rain. Without evapotranspiration data: FAO's typical value for the crop."""
    et0, week_rain = climate.get("weekEt0MmDay"), climate.get("weekRainMm")
    if et0 and week_rain:
        start = season_start(crop, climate) if start is None else start
        days = range(start, min(366, start + crop["days"]))
        gross = sum(crop_coefficient(crop, d - start) * et0[week_of(d)] for d in days)
        rain = sum(week_rain[week_of(d)] / 7 for d in days)
        source = "hargreaves"
    else:
        gross = crop["needMm"]
        rain = climate["seasonRainMm"] * min(1.0, crop["days"] / rule("season_days"))
        source = "typical"
    useful = rule("effective_rain") * rain
    return {"grossMm": round(gross, 1), "rainMm": round(rain, 1), "netMm": round(max(0.0, gross - useful), 1), "source": source}


# --- Steps 4-5. Fit, yield and gross income of one crop in one kind of year

def evaluate(crop, net, usual_net, ctx, anomaly):
    s = season_factor(anomaly, ctx["source"])
    supply = usual_net * rule("normal_year_factor")[ctx["normalYear"]] * s * position_factor(ctx["position"], s, ctx["source"])
    fit = 1.0 if net == 0 else min(1.0, supply / net)
    yield_factor = max(0.0, 1 - crop["ky"] * (1 - fit))  # FAO-33
    income = None
    price = PRICES.get(crop["id"])
    if price:
        per_ha = [t * 1000 * yield_factor * som for t, som in zip(price["yield_t_ha"], price["price_som_kg"])]
        income = {"low": round(per_ha[0] * ctx["areaHa"]), "high": round(per_ha[1] * ctx["areaHa"])}
    return {"fit": round(fit, 3), "yieldFactor": round(yield_factor, 3), "supplyMm": round(supply, 1), "income": income}


def water_left_m3(plan_net, net, area_ha):
    """Water the option leaves in the canal compared with his plan. 1 mm on 1 ha is 10 m3;
    divided by field efficiency, because water lost on the field never has to leave the canal either."""
    return round((plan_net - net) * area_ha * 10 / rule("field_efficiency"))


def rotation_note(crop, last_crops):
    last = CROPS.get(last_crops[0]) if last_crops else None
    if not last:
        return "none"
    if last["family"] == crop["family"]:
        return "warning"  # same family two seasons in a row: disease and lower yield risk
    if crop["family"] == "legume" and last["family"] == "cereal":
        return "plus"
    return "none"


def bare_months(crop):
    """Months a year the soil lies uncovered: a sign of erosion and lost moisture."""
    if crop["perennial"]:
        return 0
    if crop["winter"]:
        return 3  # sown in autumn, harvested in July
    return max(0, 12 - math.ceil(crop["days"] / 30))


# --- Step 7. What a 10-day pump stop in the peak weeks does

def pump_gap(crop):
    if crop["id"] in ("beans", "maize", "potato"):
        return "heavy"
    if crop["id"] == "alfalfa":
        return "cut"  # one cut lost
    if crop["id"] in ("safflower", "wheat"):
        return "light"
    return "unknown"


# --- Step 6. His plan, a water-saver and a soil-builder: never the same crop twice

def _option(kind, crop, needs, ctx):
    need, plan_net = needs[crop["id"]], needs[ctx["plan"]]["netMm"]
    usual = ctx["lastCrops"][0] if ctx["lastCrops"] else ctx["plan"]  # his own experience sets the normal supply
    return {
        "kind": kind,
        "crop": crop["id"],
        "need": need,
        "netNeedMm": need["netMm"],
        "normal": evaluate(crop, need["netMm"], needs[usual]["netMm"], ctx, 0.0),
        "dry": evaluate(crop, need["netMm"], needs[usual]["netMm"], ctx, ctx["dryAnomaly"]),
        "priceKnown": crop["id"] in PRICES,
        "waterLeftM3": water_left_m3(plan_net, need["netMm"], ctx["areaHa"]),
        "soil": {"nitrogen": crop["fixesN"], "bareMonths": bare_months(crop), "rotation": rotation_note(crop, ctx["lastCrops"])},
        "frostOk": crop["winter"] or crop["perennial"] or crop["days"] <= ctx["climate"]["frostFreeDays"],
        "sowing": sowing_window(crop, ctx["climate"], ctx.get("rain")),
        "pumpGap": pump_gap(crop) if ctx["source"] == "pump" else None,
    }


def _dry_income(option):
    return option["dry"]["income"]["low"] if option["dry"]["income"] else -1


def can_still_sow(crop, ctx):
    """iSEED plans next spring's season. A winter crop is sown the autumn before, so it can be
    offered only if the farmer says it is already in the ground (or it is his own plan)."""
    return not crop["winter"] or ctx.get("winterWheatSown", False) or crop["id"] == ctx["plan"]


def pick_saver(others, plan):
    """Best dry-year income among crops needing at most 70% of the plan's water (with no price known
    the thriftiest wins). If none is that thrifty, the thriftiest below the plan."""
    thrifty = [o for o in others if o["netNeedMm"] <= rule("saver_share") * plan["netNeedMm"]]
    if thrifty:
        return max(thrifty, key=lambda o: (_dry_income(o), -o["netNeedMm"]))
    return min((o for o in others if o["netNeedMm"] < plan["netNeedMm"]), key=lambda o: o["netNeedMm"], default=None)


def pick_builder(others, last_crops):
    """No rotation warning after his last two crops; a legume after a cereal first."""
    recent = {CROPS[c]["family"] for c in last_crops}
    builders = [o for o in others if CROPS[o["crop"]]["family"] not in recent]
    return max(builders, key=lambda o: (o["soil"]["rotation"] == "plus", o["soil"]["nitrogen"], _dry_income(o), -o["netNeedMm"]), default=None)


def farmer_options(ctx):
    needs = {c["id"]: water_need(c, ctx["climate"]) for c in CROPS.values()}
    plan = _option("plan", CROPS[ctx["plan"]], needs, ctx)
    others = [_option("other", c, needs, ctx) for c in CROPS.values()
              if c["id"] != ctx["plan"] and can_still_sow(c, ctx)]

    # Always three options, picked first from crops that ripen before the autumn frost.
    # Saver, if none of those fits: any thrifty crop (the card warns the season is too short), else the thriftiest.
    # Builder, if none of those fits: a crop that ripens first, then one that feeds the soil.
    ripe = [o for o in others if o["frostOk"]]
    saver = pick_saver(ripe, plan) or pick_saver(others, plan) or min(others, key=lambda o: o["netNeedMm"])
    rest = [o for o in others if o is not saver]
    builder = (pick_builder([o for o in rest if o["frostOk"]], ctx["lastCrops"])
               or max(rest, key=lambda o: (o["frostOk"], o["soil"]["nitrogen"], _dry_income(o), -o["netNeedMm"])))
    options = [plan, {**saver, "kind": "saver"}, {**builder, "kind": "builder"}]

    # Highlight the option that leaves the most water for the end of the canal, if any leaves more than 0.
    best = max(options, key=lambda o: o["waterLeftM3"])
    for o in options:
        o["highlight"] = o is best and best["waterLeftM3"] > 0
    return {
        "options": options,
        "planEarnsMost": plan["priceKnown"] and all(_dry_income(plan) >= _dry_income(o) for o in options[1:]),
        "scenarios": scenarios(ctx),
        "doubleCrop": double_crop(ctx, needs) if can_still_sow(CROPS["wheat"], ctx) else None,
        "frostTrend": frost_trend(ctx["climate"]),
    }


def scenarios(ctx):
    """The two years every option is priced for, with the factors used, so the screen can show them."""
    out = {}
    for name, anomaly in (("normal", 0.0), ("dry", ctx["dryAnomaly"])):
        s = season_factor(anomaly, ctx["source"])
        out[name] = {"snowAnomaly": anomaly, "s": round(s, 3), "p": round(position_factor(ctx["position"], s, ctx["source"]), 3)}
    return out


# --- Step 10. Two crops in one year: winter wheat (already sown), then a short summer crop

def double_crop(ctx, needs):
    """The best second crop that still matures before the autumn frost, or None where the season is too short."""
    climate, wheat = ctx["climate"], CROPS["wheat"]
    harvest = wheat_regrowth(wheat, climate) + wheat["days"]
    window = climate["firstAutumnFrostDoy"] - harvest
    fits = [c for c in CROPS.values() if not (c["winter"] or c["perennial"])
            and c["days"] + rule("double_crop_spare_days") <= window]
    if not fits:
        return None
    second = max(fits, key=lambda c: (c["id"] in PRICES, c["fixesN"], -c["days"]))
    net = needs["wheat"]["netMm"] + water_need(second, climate, start=harvest + 1)["netMm"]
    return {
        "first": "wheat", "second": second["id"],
        "wheatHarvest": month_day(harvest), "windowDays": window,
        "netNeedMm": round(net, 1),
        "waterLeftM3": water_left_m3(needs[ctx["plan"]]["netMm"], net, ctx["areaHa"]),
    }


# --- Step 8. Field check: can I plant here? Each check is good / careful / no; the verdict is the worst.

def soil_class(site):
    cut = rule("soil_class")
    if not site or site["sandPct"] + site["clayPct"] == 0:
        return "unknown"
    if site["sandPct"] >= cut["sandy_sand_pct"]:
        return "sandy"
    return "clay" if site["clayPct"] >= cut["clay_clay_pct"] else "medium"


def field_check(site, soil_answer=None, crop=None, climate=None, sowing=None):
    """`site` comes from the grids; the crop checks (frost, heavy rain) are added when a crop is given."""
    checks = []
    add = lambda cid, level, value, source: checks.append({"id": cid, "level": level, "value": value, "source": source})
    if site:
        slope, cut = site["slopeDeg"], rule("slope_deg")
        hay = crop and crop["perennial"]  # hay holds a slope that row crops would lose
        add("slope", "good" if slope < cut["careful"] else "careful" if slope <= cut["no"] or hay else "no", slope, "srtm")

        half = site["ndviYears"] / 2
        level = "good" if site["greenYears"] > half else "no" if site["bareYears"] > half else "careful"
        add("green", level, {"greenYears": site["greenYears"], "bareYears": site["bareYears"], "years": site["ndviYears"]}, "modis")

    soil = soil_answer if soil_answer in ("sandy", "medium", "clay") else soil_class(site)
    if soil != "unknown":
        add("soil", "good" if soil == "medium" else "careful", soil, "farmer" if soil == soil_answer else "soilgrids")

    if crop and climate and not (crop["winter"] or crop["perennial"]):
        spare = climate["frostFreeDays"] - crop["days"]
        add("frost", "good" if spare >= rule("frost_spare_days") else "careful" if spare >= 0 else "no", spare, "power")
    if sowing and sowing.get("heavyRain"):
        share, cut = sowing["heavyRain"]["maxShare"], rule("heavy_rain_share")
        steep = site and site["slopeDeg"] > rule("slope_deg")["careful"]
        add("heavyRain", "good" if share < cut["careful"] else "no" if share > cut["no"] and steep else "careful", share, "imerg")

    if not checks:
        return None
    return {"verdict": max((c["level"] for c in checks), key=LEVELS.index), "checks": checks}


# --- Step 2. Water manager: what the basin's snow means for his canal

def manager_view(anomaly, source, normal_turns, villages, main_crop, climate):
    s = season_factor(anomaly, source)
    ha = sum(v["ha"] for v in villages)
    demand = water_need(CROPS[main_crop], climate)["netMm"] * ha * 10 / rule("field_efficiency")
    positions = []
    for position in POSITIONS:
        fit = min(1.0, s * position_factor(position, s, source))
        positions.append({"position": position, "fit": round(fit, 3), "short": fit < rule("short_fit")})
    return {
        "s": round(s, 3),
        "normalTurns": normal_turns,
        "expectedTurns": math.floor(normal_turns * s + 1e-9),
        "totalHa": ha,
        "demandM3": round(demand),
        "expectedM3": round(demand * min(1.0, s)),
        "shortM3": round(demand * max(0.0, 1 - s)),
        "enough": not any(p["short"] for p in positions),
        "positions": positions,
    }
