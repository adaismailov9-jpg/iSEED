"""Deterministic rules from ТЗ section 4. No AI, no randomness: same input, same answer."""
import csv
import json
import math
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).parent / "data"
RULES = json.loads((DATA / "rules.json").read_text(encoding="utf-8"))
PRICES = json.loads((DATA / "prices.json").read_text(encoding="utf-8"))


def _load_crops():
    crops = {}
    with open(DATA / "crops.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            crops[r["id"]] = {
                "id": r["id"],
                "family": r["family"],
                "fixesN": r["fixes_n"] == "1",
                "winter": r["winter"] == "1",
                "perennial": r["perennial"] == "1",
                "days": int(r["days"]),
                "needMm": float(r["need_mm"]),
                "ky": float(r["ky"]),
                "minSowTempC": float(r["min_sow_temp_c"]) if r["min_sow_temp_c"] else None,
                "daysToFlower": int(r["days_to_flower"]) if r["days_to_flower"] else None,
                "source": r["source"],
            }
    return crops


CROPS = _load_crops()
POSITIONS = ("start", "middle", "end")
SOURCES = ("gravity", "pump", "well")


def rule(key):
    return RULES[key]["value"]


# Step 1. Season water factor S, from the basin's snow anomaly (-0.2 = 20% below normal)
def season_factor(anomaly, source):
    if source == "well":
        return 1.0
    limits = rule("snow_factor_limits")
    s = min(limits["max"], max(limits["min"], 1 + rule("snow_sensitivity") * anomaly))
    if source == "pump":  # a pump on a big river feels a snow deficit less
        s = 1 - rule("pump_softening") * (1 - s)
    return s


# Step 2. Canal position factor P: the share of the allocation that reaches the field.
# The end of the canal loses more the shorter the season is.
def position_factor(position, s, source):
    if source == "well":
        return 1.0
    p = rule("position_factor")[position]
    low_at = rule("position_low_at")
    dryness = min(1.0, max(0.0, (1 - s) / (1 - low_at)))
    return p["normal"] + (p["low"] - p["normal"]) * dryness


# Step 3. Crop water need after useful rain (mm per season)
def net_need_mm(crop, climate):
    share = min(1.0, crop["days"] / rule("season_days"))
    return max(0.0, crop["needMm"] - rule("effective_rain") * climate["seasonRainMm"] * share)


# Steps 4-5. Fit, yield factor and gross income of one crop in one kind of year
def evaluate(crop, usual, ctx, anomaly):
    net = net_need_mm(crop, ctx["climate"])
    normal_supply = net_need_mm(usual, ctx["climate"]) * rule("normal_year_factor")[ctx["normalYear"]]
    s = season_factor(anomaly, ctx["source"])
    supply = normal_supply * s * position_factor(ctx["position"], s, ctx["source"])
    fit = 1.0 if net == 0 else min(1.0, supply / net)
    yield_factor = max(0.0, 1 - crop["ky"] * (1 - fit))
    price = PRICES.get(crop["id"])
    income = None
    if price:
        per_ha = [y * 1000 * yield_factor * p for y, p in zip(price["yield_t_ha"], price["price_som_kg"])]
        income = {"low": round(per_ha[0] * ctx["areaHa"]), "high": round(per_ha[1] * ctx["areaHa"])}
    return {"fit": round(fit, 3), "yieldFactor": round(yield_factor, 3), "supplyMm": round(supply, 1), "income": income}


def rotation_note(crop, last_crops):
    last = CROPS.get(last_crops[0]) if last_crops else None
    if not last:
        return "none"
    if last["family"] == crop["family"]:
        return "warning"  # same family two seasons in a row
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


def _option(kind, crop, usual, plan, ctx):
    normal = evaluate(crop, usual, ctx, 0.0)
    dry = evaluate(crop, usual, ctx, ctx["dryAnomaly"])
    net, plan_net = net_need_mm(crop, ctx["climate"]), net_need_mm(plan, ctx["climate"])
    return {
        "kind": kind,
        "crop": crop["id"],
        "netNeedMm": round(net, 1),
        "normal": normal,
        "dry": dry,
        "priceKnown": crop["id"] in PRICES,
        # 1 mm on 1 ha is 10 m3; divided by field efficiency because that water never has to leave the canal
        "waterLeftM3": round((plan_net - net) * ctx["areaHa"] * 10 / rule("field_efficiency")),
        "soil": {
            "nitrogen": crop["fixesN"],
            "bareMonths": bare_months(crop),
            "rotation": rotation_note(crop, ctx["lastCrops"]),
        },
        "frostOk": crop["winter"] or crop["perennial"] or crop["days"] <= ctx["climate"]["frostFreeDays"],
        "sowing": sowing_window(crop, ctx["climate"], ctx.get("rain")),
        "pumpGap": pump_gap(crop) if ctx["source"] == "pump" else None,
    }


def _dry_income(opt):
    return opt["dry"]["income"]["low"] if opt["dry"]["income"] else -1


# Step 6. His plan, a water-saver and a soil-builder: never the same crop twice.
def farmer_options(ctx):
    plan = CROPS[ctx["plan"]]
    usual = CROPS.get(ctx["lastCrops"][0] if ctx["lastCrops"] else "") or plan
    build = lambda kind, crop: _option(kind, crop, usual, plan, ctx)
    options = [build("plan", plan)]
    plan_net = options[0]["netNeedMm"]

    others = [build("other", c) for c in CROPS.values() if c["id"] != plan["id"]]
    others = [o for o in others if o["frostOk"]]

    # Water-saver: best dry-year income among crops needing at most 70% of the plan's water.
    # With no price known the thriftiest crop wins. If none is that thrifty, the thriftiest below the plan.
    savers = [o for o in others if o["netNeedMm"] <= rule("saver_share") * plan_net]
    if not savers:
        savers = sorted((o for o in others if o["netNeedMm"] < plan_net), key=lambda o: o["netNeedMm"])[:1]
    saver = max(savers, key=lambda o: (_dry_income(o), -o["netNeedMm"]), default=None)
    if saver:
        options.append({**saver, "kind": "saver"})

    # Soil-builder: no rotation warning after his last two crops; a legume after a cereal first.
    recent = {CROPS[c]["family"] for c in ctx["lastCrops"] if c in CROPS}
    builders = [o for o in others if o is not saver and CROPS[o["crop"]]["family"] not in recent]
    builder = max(builders, key=lambda o: (o["soil"]["rotation"] == "plus", o["soil"]["nitrogen"], _dry_income(o), -o["netNeedMm"]), default=None)
    if builder:
        options.append({**builder, "kind": "builder"})

    # Highlight the option that leaves the most water; the plan itself if nothing leaves more than 0.
    best = max(options, key=lambda o: o["waterLeftM3"])
    for o in options:
        o["highlight"] = o is best and best["waterLeftM3"] > 0
    plan_best = all(_dry_income(options[0]) >= _dry_income(o) for o in options[1:])
    return {"options": options, "planEarnsMost": plan_best and options[0]["priceKnown"], "scenarios": scenarios(ctx)}


def scenarios(ctx):
    """The two years every option is priced for, with the factors used, so the screen can show them."""
    out = {}
    for name, anomaly in (("normal", 0.0), ("dry", ctx["dryAnomaly"])):
        s = season_factor(anomaly, ctx["source"])
        out[name] = {"snowAnomaly": anomaly, "s": round(s, 3), "p": round(position_factor(ctx["position"], s, ctx["source"]), 3)}
    return out


# Step 7. What a 10-day pump stop in the peak weeks does
def pump_gap(crop):
    if crop["id"] in ("beans", "maize", "potato"):
        return "heavy"
    if crop["id"] == "alfalfa":
        return "cut"
    if crop["id"] in ("safflower", "wheat"):
        return "light"
    return "unknown"


# Step 9. Sowing window from NASA POWER weekly climate. Dates are month-day of the next season.
def _md(doy):
    return (date(2027, 1, 1) + timedelta(days=int(doy) - 1)).strftime("%m-%d")


def sowing_window(crop, climate, rain=None):
    weeks = climate.get("weekMeanTempC")
    if crop["winter"] or crop["minSowTempC"] is None or not weeks:
        return None
    last_frost, first_frost = climate["lastSpringFrostDoy"], climate["firstAutumnFrostDoy"]
    week = max(0, (last_frost - 1) // 7)
    while week < 51 and weeks[week] < crop["minSowTempC"]:
        week += 1
    earliest = max(last_frost + 1, week * 7 + 1)
    latest = first_frost - crop["days"]
    out = {"earliest": _md(earliest), "latest": _md(latest) if latest >= earliest else None, "fits": latest >= earliest}
    if crop["daysToFlower"]:
        flower = earliest + crop["daysToFlower"]
        hot = climate["weekHotDays"][min(51, (flower - 1) // 7)]
        out["flowering"] = {"date": _md(flower), "hotDays": hot, "tooHot": hot >= rule("heat_days_week")}
    if rain:
        # Sowing weeks: from the earliest date, at most `sowing_weeks`, never past the latest date.
        first = (earliest - 1) // 7
        last = min(first + rule("sowing_weeks") - 1, max(first, (latest - 1) // 7), 51)
        share = rain["weekHeavyShare"]
        best = min(range(first, last + 1), key=lambda w: (share[w], w))
        out["heavyRain"] = {
            "maxShare": max(share[first:last + 1]),
            "suggested": _md(max(earliest, best * 7 + 1)),
            "riskyWeeks": [_md(w * 7 + 1) for w in range(first, last + 1) if share[w] >= rule("heavy_rain_share")["no"]],
        }
    return out


# Step 8. Field check: can I plant here? Each check is good / careful / no; the verdict is the worst.
LEVELS = ("good", "careful", "no")


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
        hay = crop and crop["perennial"]
        level = "good" if slope < cut["careful"] else "careful" if slope <= cut["no"] or hay else "no"
        add("slope", level, slope, "srtm")

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
        level = "good" if share < cut["careful"] else "no" if share > cut["no"] and steep else "careful"
        add("heavyRain", level, share, "imerg")

    if not checks:
        return None
    return {"verdict": max((c["level"] for c in checks), key=LEVELS.index), "checks": checks}


# Step 2. Water manager: what the basin's snow means for his canal
def manager_view(anomaly, source, normal_turns, villages, main_crop, climate):
    s = season_factor(anomaly, source)
    ha = sum(v["ha"] for v in villages)
    demand = net_need_mm(CROPS[main_crop], climate) * ha * 10 / rule("field_efficiency")
    positions = []
    for pos in POSITIONS:
        fit = min(1.0, s * position_factor(pos, s, source))
        positions.append({"position": pos, "fit": round(fit, 3), "short": fit < rule("short_fit")})
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
