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


# Step 1. Season water factor S
def season_factor(level, source):
    if source == "well":
        return 1.0
    s = rule("snow_factor")[level]
    if source == "pump":
        s = 1 - rule("pump_softening") * (1 - s)
    return s


# Step 2. Canal position factor P
def position_factor(position, level, source):
    if source == "well":
        return 1.0
    return rule("position_factor")[position]["low" if level == "low" else "normal"]


# Step 3. Crop water need after useful rain (mm per season)
def net_need_mm(crop, climate):
    share = min(1.0, crop["days"] / rule("season_days"))
    return max(0.0, crop["needMm"] - rule("effective_rain") * climate["seasonRainMm"] * share)


# Steps 4-5. Fit, yield factor and gross income of one crop in one kind of year
def evaluate(crop, usual, ctx, level):
    net = net_need_mm(crop, ctx["climate"])
    normal_supply = net_need_mm(usual, ctx["climate"]) * rule("normal_year_factor")[ctx["normalYear"]]
    supply = normal_supply * season_factor(level, ctx["source"]) * position_factor(ctx["position"], level, ctx["source"])
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


def _option(kind, crop, usual, plan, ctx):
    normal = evaluate(crop, usual, ctx, "normal")
    dry = evaluate(crop, usual, ctx, "low")
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
            "bareMonths": 0 if crop["perennial"] else max(0, 12 - math.ceil(crop["days"] / 30)) if not crop["winter"] else 3,
            "rotation": rotation_note(crop, ctx["lastCrops"]),
        },
        "frostOk": crop["winter"] or crop["perennial"] or crop["days"] <= ctx["climate"]["frostFreeDays"],
        "sowing": sowing_window(crop, ctx["climate"]),
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
    return {"options": options, "planEarnsMost": plan_best and options[0]["priceKnown"]}


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


def sowing_window(crop, climate):
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
    return out


# Step 2. Water manager: what the basin's snow means for his canal
def manager_view(level, source, normal_turns, villages, main_crop, climate):
    s = season_factor(level, source)
    crop = CROPS[main_crop]
    ha = sum(v["ha"] for v in villages)
    demand = net_need_mm(crop, climate) * ha * 10 / rule("field_efficiency")
    positions = []
    for pos in POSITIONS:
        fit = min(1.0, s * position_factor(pos, level, source))
        positions.append({"position": pos, "fit": round(fit, 3), "short": fit < rule("short_fit")})
    return {
        "s": round(s, 3),
        "normalTurns": normal_turns,
        "expectedTurns": math.floor(normal_turns * s),
        "totalHa": ha,
        "demandM3": round(demand),
        "expectedM3": round(demand * min(1.0, s)),
        "shortM3": round(demand * max(0.0, 1 - s)),
        "enough": s >= 1,
        "positions": positions,
    }
