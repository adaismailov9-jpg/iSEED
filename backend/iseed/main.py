"""iSEED API. Shapes are in CLAUDE.md. Routes answer at /x (dev proxy) and /api/x (Vercel)."""
from functools import lru_cache

from fastapi import APIRouter, FastAPI, Header, Request
from fastapi.responses import JSONResponse

from . import engine, geo
from .climate import basin_at, climate_at, load, rain_at
from .grid import site_at
from .storage import open_store

VERSION = "0.2.0"
MESSAGE_MAX = 280
app = FastAPI(title="iSEED")
api = APIRouter()
store = lru_cache(open_store)  # opened on first use


class ApiError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


@app.exception_handler(ApiError)
async def api_error(_: Request, err: ApiError):
    return JSONResponse({"code": err.code, "message": err.message}, status_code=err.status)


def need(body, key, allowed=None):
    value = body.get(key)
    if value is None or value == "" or (allowed is not None and value not in allowed):
        hint = f": one of {', '.join(allowed)}" if allowed else ""
        raise ApiError(422, "bad_input", f"'{key}' is missing or wrong{hint}")
    return value


def user_of(authorization, role=None, required=True):
    token = (authorization or "").removeprefix("Bearer ").strip()
    user = store().user_for_token(token) if token else None
    if not user and required:
        raise ApiError(401, "not_signed_in", "Sign in first")
    if user and role and user["role"] != role:
        raise ApiError(403, "wrong_role", f"Only a {role} can do this")
    return user


def without_series(snow):
    return snow and {k: v for k, v in snow.items() if k != "series"}


def snow_for(basin):
    """The basin's entry in data/snow.json, or None."""
    snow = load("snow.json")
    return snow["basins"].get(basin) if snow and basin else None


def climate_or_fail(lat, lon, elev):
    climate = climate_at(lat, lon, elev)
    if not climate:
        raise ApiError(503, "data_missing", "data/climate.json is not built yet (scripts/power_job.py)")
    return climate


def climate_evidence(climate):
    keys = ("seasonRainMm", "frostFreeDays", "lastSpringFrostDoy", "firstAutumnFrostDoy", "elevM", "cell",
            "heightKnown", "source", "window", "computed")
    return {k: climate[k] for k in keys}


def place(body, authorization=None):
    """Where the request is about: a saved field, an outline, or a point with hectares."""
    if body.get("fieldId") is not None:
        field = store().field(body["fieldId"])
        if not field:
            raise ApiError(404, "no_field", "This field does not exist")
        return field
    if body.get("geometry"):
        try:
            points = geo.ring_of(body["geometry"])
            assert len(points) >= 3
        except Exception:
            raise ApiError(422, "bad_input", "'geometry' must be a GeoJSON Polygon with at least 3 corners")
        (lat, lon), area = geo.centroid(points), geo.area_ha(points)
    else:
        lat, lon, area, points = need(body, "lat"), need(body, "lon"), need(body, "areaHa"), None
    if not isinstance(area, (int, float)) or area <= 0:
        raise ApiError(422, "bad_input", "The field area must be above 0")
    site = site_at(points or [(lat, lon)])
    return {
        "lat": round(lat, 5), "lon": round(lon, 5), "areaHa": round(area, 2),
        "elevM": body.get("elevM") or (site and site["elevM"]),
        "basin": basin_at(lat, lon),
        "site": site,
        "geometry": body.get("geometry"),
    }


# --- accounts

@api.post("/register")
def register(body: dict):
    pin = str(need(body, "pin"))
    if not (pin.isdigit() and len(pin) == 4):
        raise ApiError(422, "bad_input", "'pin' must be 4 digits")
    user = store().create_user(need(body, "name"), need(body, "role", ("farmer", "manager")),
                               need(body, "region"), need(body, "village"), pin)
    if not user:
        raise ApiError(409, "name_taken", "This name is already registered")
    return {"token": store().create_session(user["id"]), "user": user}


@api.post("/login")
def login(body: dict):
    user = store().check_pin(need(body, "name"), str(need(body, "pin")))
    if not user:
        raise ApiError(401, "wrong_login", "Wrong name or PIN")
    return {"token": store().create_session(user["id"]), "user": user}


# --- data

@api.get("/health")
def health():
    files = {k: load(f"{k}.json") for k in ("climate", "snow", "rain_weeks")}
    return {"version": VERSION, "data": {k: v and v["computed"] for k, v in files.items()}}


@api.get("/crops")
def crops():
    return {"crops": list(engine.CROPS.values()), "prices": engine.PRICES, "rules": engine.RULES}


@api.get("/basin")
def basin(lat: float, lon: float):
    found = basin_at(lat, lon)
    if not found:
        raise ApiError(404, "no_basin", "This point is outside the river basins of Kyrgyzstan")
    return {"basin": found, "snow": without_series(snow_for(found))}


@api.get("/snow")
def snow(basin: str):
    found = snow_for(basin)
    if not found:
        raise ApiError(404, "no_basin", "No snow signal for this basin")
    return without_series(found)


@api.get("/hindcast")
def hindcast(basin: str):
    found = snow_for(basin)
    if not found:
        raise ApiError(404, "no_basin", "No snow series for this basin")
    return {**found, "shortYears": load("snow.json")["shortYears"]}


# --- fields

@api.post("/fields")
def add_field(body: dict, authorization: str = Header(None)):
    user = user_of(authorization, required=False)
    field = place(body)
    field["fieldCheck"] = engine.field_check(field["site"])
    if user:
        field = {"id": store().save_field(user["id"], field), **field}
    return field


@api.get("/fields")
def list_fields(authorization: str = Header(None)):
    return {"fields": store().fields_of(user_of(authorization)["id"])}


# --- water manager

@api.post("/manager")
def manager(body: dict, authorization: str = Header(None)):
    user = user_of(authorization, required=False)
    villages = need(body, "villages")
    if not villages or any(not v.get("name") or not isinstance(v.get("ha"), (int, float)) or v["ha"] <= 0 for v in villages):
        raise ApiError(422, "bad_input", "'villages' needs at least one {name, ha} with ha above 0")
    source = need(body, "source", ("gravity", "pump"))
    turns = need(body, "normalTurns")
    main_crop = body.get("mainCrop", "beans")
    if main_crop not in engine.CROPS:
        raise ApiError(422, "bad_input", "'mainCrop' is not in the crop table")
    lat, lon = need(body, "lat"), need(body, "lon")
    basin_id = body.get("basin") or basin_at(lat, lon)
    snow_now = snow_for(basin_id)
    if not snow_now:
        raise ApiError(404, "no_basin", "This point is outside the river basins of Kyrgyzstan")
    site = site_at([(lat, lon)])
    climate = climate_or_fail(lat, lon, body.get("elevM") or (site and site["elevM"]))
    if user and user["role"] == "manager":
        store().save_canal(user["id"], {"villages": villages, "source": source, "normalTurns": turns,
                                        "mainCrop": main_crop, "lat": lat, "lon": lon})
    view = engine.manager_view(snow_now["level"], source, turns, villages, main_crop, climate)
    return {**view, "mainCrop": main_crop, "basin": basin_id, "snow": without_series(snow_now),
            "evidence": {"rules": engine.RULES, "climate": climate_evidence(climate)}}


@api.get("/manager")
def manager_canal(authorization: str = Header(None)):
    """The canal the signed-in manager saved, or null."""
    return {"canal": store().canal_of(user_of(authorization, "manager")["id"])}


@api.post("/manager/message")
def post_message(body: dict, authorization: str = Header(None)):
    user = user_of(authorization, "manager")
    text = str(need(body, "text")).strip()
    if not text or len(text) > MESSAGE_MAX:
        raise ApiError(422, "bad_input", f"'text' must be 1 to {MESSAGE_MAX} characters")
    return store().set_message(user["id"], text)


@api.get("/message")
def message(village: str):
    return {"message": store().message_for(village)}


# --- farmer

@api.post("/farmer")
def farmer(body: dict, authorization: str = Header(None)):
    user = user_of(authorization, required=False)
    field = place(body)
    plan = need(body, "plan", tuple(engine.CROPS))
    rain = rain_at(field["lat"], field["lon"])
    ctx = {
        "areaHa": field["areaHa"],
        "position": need(body, "position", engine.POSITIONS),
        "source": need(body, "source", engine.SOURCES),
        "normalYear": need(body, "normalYear", ("enough", "sometimes", "often", "unknown")),
        "plan": plan,
        "lastCrops": [c for c in body.get("lastCrops", []) if c in engine.CROPS][:2],
        "climate": climate_or_fail(field["lat"], field["lon"], field["elevM"]),
        "rain": rain,
    }
    result = engine.farmer_options(ctx)
    check = engine.field_check(field["site"], body.get("soil"), engine.CROPS[plan], ctx["climate"], result["options"][0]["sowing"])
    return {
        "input": {k: v for k, v in ctx.items() if k not in ("climate", "rain")},
        "field": {k: field[k] for k in ("lat", "lon", "areaHa", "elevM", "basin")},
        "message": store().message_for(user["village"]) if user else None,
        "fieldCheck": check,
        **result,
        "basin": field["basin"],
        "snow": without_series(snow_for(field["basin"])),
        "evidence": {
            "rules": engine.RULES,
            "prices": engine.PRICES,
            "climate": climate_evidence(ctx["climate"]),
            "rain": rain and {k: rain[k] for k in ("source", "window", "heavyMm", "summerDrySpellDays", "computed")},
            "site": field["site"],
            "formula": "supply = net need of usual crop x A x S x P; fit = min(1, supply / net need); "
                       "yield = 1 - Ky x (1 - fit); income = yield t/ha x price x ha (gross, costs not counted); "
                       "water left = (net need of plan - net need of option) x ha x 10 / field efficiency",
        },
    }


app.include_router(api)
app.include_router(api, prefix="/api")
