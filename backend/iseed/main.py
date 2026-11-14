"""iSEED API. Shapes are in CLAUDE.md. Routes answer at /x (dev proxy) and /api/x (Vercel)."""
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from . import engine
from .climate import basin_at, climate_at, load

VERSION = "0.1.0"
app = FastAPI(title="iSEED")
api = APIRouter()


class ApiError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


@app.exception_handler(ApiError)
async def api_error(_: Request, err: ApiError):
    return JSONResponse({"code": err.code, "message": err.message}, status_code=err.status)


def need(body, key, allowed=None):
    value = body.get(key)
    if value is None or (allowed is not None and value not in allowed):
        hint = f": one of {', '.join(allowed)}" if allowed else ""
        raise ApiError(422, "bad_input", f"'{key}' is missing or wrong{hint}")
    return value


def climate_or_fail(lat, lon, elev):
    climate = climate_at(lat, lon, elev)
    if not climate:
        raise ApiError(503, "data_missing", "data/climate.json is not built yet (scripts/power_job.py)")
    return climate


def snow_for(basin):
    """The basin's entry in data/snow.json, or None until scripts/snow_job.py has run."""
    snow = load("snow.json")
    return snow["basins"].get(basin) if snow and basin else None


@api.get("/health")
def health():
    climate, snow = load("climate.json"), load("snow.json")
    return {"version": VERSION, "data": {"climate": climate and climate["computed"], "snow": snow and snow["computed"]}}


@api.get("/crops")
def crops():
    return {"crops": list(engine.CROPS.values()), "prices": engine.PRICES, "rules": engine.RULES}


@api.get("/snow")
def snow(basin: str):
    found = snow_for(basin)
    if not found:
        raise ApiError(503, "data_missing", "data/snow.json has no snow signal for this basin yet")
    return {k: v for k, v in found.items() if k != "series"}


@api.get("/hindcast")
def hindcast(basin: str):
    found = snow_for(basin)
    if not found:
        raise ApiError(503, "data_missing", "data/snow.json has no snow series for this basin yet")
    return found


@api.get("/basin")
def basin(lat: float, lon: float):
    found = basin_at(lat, lon)
    if not found:
        raise ApiError(404, "no_basin", "This point is outside the river basins of Kyrgyzstan")
    return {"basin": found, "snow": (lambda s: s and {k: v for k, v in s.items() if k != "series"})(snow_for(found))}


@api.post("/manager")
def manager(body: dict):
    villages = need(body, "villages")
    if not villages or any(not isinstance(v.get("ha"), (int, float)) or v["ha"] <= 0 for v in villages):
        raise ApiError(422, "bad_input", "'villages' needs at least one {name, ha} with ha above 0")
    source = need(body, "source", ("gravity", "pump"))
    turns = need(body, "normalTurns")
    main_crop = body.get("mainCrop", "beans")
    if main_crop not in engine.CROPS:
        raise ApiError(422, "bad_input", "'mainCrop' is not in the crop table")
    basin_id = body.get("basin") or basin_at(need(body, "lat"), need(body, "lon"))
    snow_now = snow_for(basin_id)
    if not snow_now:
        raise ApiError(503, "data_missing", "data/snow.json has no snow signal for this basin yet")
    climate = climate_or_fail(need(body, "lat"), need(body, "lon"), body.get("elevM"))
    view = engine.manager_view(snow_now["level"], source, turns, villages, main_crop, climate)
    return {**view, "mainCrop": main_crop, "snow": {k: v for k, v in snow_now.items() if k != "series"},
            "evidence": {"rules": engine.RULES, "climate": _climate_evidence(climate)}}


def _climate_evidence(climate):
    keys = ("seasonRainMm", "frostFreeDays", "lastSpringFrostDoy", "firstAutumnFrostDoy", "elevM", "cell",
            "heightKnown", "source", "window", "computed")
    return {k: climate[k] for k in keys}


@api.post("/farmer")
def farmer(body: dict):
    area = need(body, "areaHa")
    if not isinstance(area, (int, float)) or area <= 0:
        raise ApiError(422, "bad_input", "'areaHa' must be above 0")
    last = [c for c in body.get("lastCrops", []) if c in engine.CROPS][:2]
    ctx = {
        "areaHa": area,
        "position": need(body, "position", engine.POSITIONS),
        "source": need(body, "source", engine.SOURCES),
        "normalYear": need(body, "normalYear", ("enough", "sometimes", "often", "unknown")),
        "plan": need(body, "plan", tuple(engine.CROPS)),
        "lastCrops": last,
        "climate": climate_or_fail(need(body, "lat"), need(body, "lon"), body.get("elevM")),
    }
    result = engine.farmer_options(ctx)
    basin_id = body.get("basin") or basin_at(body["lat"], body["lon"])
    snow_now = snow_for(basin_id)
    return {
        "basin": basin_id,
        "input": {k: v for k, v in ctx.items() if k != "climate"},
        **result,
        "snow": snow_now and {k: v for k, v in snow_now.items() if k != "series"},
        "evidence": {
            "rules": engine.RULES,
            "prices": engine.PRICES,
            "climate": _climate_evidence(ctx["climate"]),
            "formula": "supply = net need of usual crop x A x S x P; fit = min(1, supply / net need); "
                       "yield = 1 - Ky x (1 - fit); income = yield t/ha x price x ha (gross, costs not counted)",
        },
    }


app.include_router(api)
app.include_router(api, prefix="/api")
