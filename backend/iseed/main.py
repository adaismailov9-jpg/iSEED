"""iSEED API. Shapes are in CLAUDE.md. Routes answer at /x (dev proxy) and /api/x (Vercel)."""
import logging
import os
import sqlite3
from datetime import timedelta
from functools import lru_cache

from fastapi import APIRouter, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import engine, geo, storage
from .climate import basin_at, climate_at, load, rain_at
from .grid import site_at
from .storage import open_store

VERSION = "0.2.0"
MESSAGE_MAX = 280
# /login limit: a 4-digit PIN has only 10,000 values, so wrong guesses are counted in the store
# (shared by every server instance). Over the limit, /login answers 429 until old failures age out.
LOGIN_WINDOW = timedelta(minutes=15)
LOGIN_MAX_PER_NAME = 5    # wrong PINs for one name
LOGIN_MAX_PER_IP = 20     # wrong PINs from one address, across names (stops "1234 for everyone")
app = FastAPI(title="iSEED")
api = APIRouter()
store = lru_cache(open_store)  # opened on first use


class ApiError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


@app.exception_handler(ApiError)
async def api_error(_: Request, err: ApiError):
    return JSONResponse({"code": err.code, "message": err.message}, status_code=err.status)


@app.exception_handler(RequestValidationError)
async def bad_request(_: Request, err: RequestValidationError):
    """FastAPI's own checks (a path id that is not a number, a body that is not JSON) in the same error shape."""
    first = (err.errors() or [{}])[0]
    where = ".".join(str(x) for x in first.get("loc", ()) if x not in ("body", "query", "path"))
    message = f"'{where}' is missing or wrong" if where else "The request body must be a JSON object"
    return JSONResponse({"code": "bad_input", "message": message}, status_code=422)


async def db_unavailable(_: Request, err: Exception):
    """The database cannot be reached (down, waking up, wrong DATABASE_URL): a clear 503 in the usual
    error shape instead of a bare 500. The real error goes to the server log (Vercel: Logs)."""
    logging.getLogger("iseed").error("database unavailable: %s", err)
    return JSONResponse({"code": "db_unavailable", "message": "The database is not reachable. Try again in a minute"},
                        status_code=503)


app.add_exception_handler(sqlite3.OperationalError, db_unavailable)
try:  # SQLAlchemy is only needed for PostgresStore
    from sqlalchemy.exc import InterfaceError, OperationalError
    app.add_exception_handler(OperationalError, db_unavailable)
    app.add_exception_handler(InterfaceError, db_unavailable)
except ImportError:
    pass


def need(body, key, allowed=None):
    value = body.get(key)
    if value is None or value == "" or (allowed is not None and value not in allowed):
        hint = f": one of {', '.join(allowed)}" if allowed else ""
        raise ApiError(422, "bad_input", f"'{key}' is missing or wrong{hint}")
    return value


def text_of(body, key):
    """A text value that is not blank once spaces are trimmed."""
    value = need(body, key)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(422, "bad_input", f"'{key}' must be text")
    return value


def pin_of(body, key):
    pin = str(need(body, key))
    if not (pin.isdigit() and len(pin) == 4):
        raise ApiError(422, "bad_input", f"'{key}' must be 4 digits")
    return pin


def check_id(value, key="fieldId"):
    """Ids are whole numbers that fit the database's 64-bit id column."""
    if not isinstance(value, int) or isinstance(value, bool) or not 0 < value < 2**63:
        raise ApiError(422, "bad_input", f"'{key}' must be a whole number")
    return value


def login_limit(name, ip):
    """429 while this name or this address has too many recent wrong PINs (see LOGIN_* above)."""
    by_name, by_ip = store().failed_logins(name, ip, storage.utcnow() - LOGIN_WINDOW)
    if by_name >= LOGIN_MAX_PER_NAME or by_ip >= LOGIN_MAX_PER_IP:
        raise ApiError(429, "too_many_tries", "Too many wrong PINs. Try again in 15 minutes")


def confirm_pin(user, pin, request):
    """For account changes that need the current PIN. Wrong tries count toward the /login limit,
    so these routes are no way around it."""
    ip = client_ip(request)
    login_limit(user["name"], ip)
    if not store().check_pin(user["name"], str(pin)):
        store().add_failed_login(user["name"], ip)
        raise ApiError(403, "wrong_pin", "The current PIN is wrong")


def token_of(authorization):
    return (authorization or "").removeprefix("Bearer ").strip()


def client_ip(request: Request):
    """The caller's address. On Vercel the platform sets X-Forwarded-For; elsewhere a client could
    fake that header, so it is ignored and the socket address is used."""
    if os.environ.get("VERCEL"):
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if forwarded:
            return forwarded
    return request.client.host if request.client else "unknown"


def user_of(authorization, role=None, required=True):
    token = token_of(authorization)
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


def dry_year(basin):
    """The low-snow year the farmer's options are priced for: the mean of the basin's own low years."""
    snow = snow_for(basin)
    lows = [p for p in (snow["series"] if snow else []) if p["level"] == "low" and p["year"] < int(snow["month"][:4])]
    if not lows:
        return {"anomaly": engine.rule("dry_year_anomaly"), "years": [], "basin": None}
    mean = sum(p["volumeKm3"] for p in lows) / len(lows)
    return {"anomaly": round(mean / snow["normalKm3"] - 1, 3), "years": [p["year"] for p in lows], "basin": basin}


def climate_or_fail(lat, lon, elev):
    climate = climate_at(lat, lon, elev)
    if not climate:
        raise ApiError(503, "data_missing", "data/climate.json is not built yet (scripts/power_job.py)")
    return climate


def climate_evidence(climate):
    keys = ("seasonRainMm", "frostFreeDays", "lastSpringFrostDoy", "firstAutumnFrostDoy", "elevM", "cell",
            "heightKnown", "source", "window", "computed")
    return {k: climate[k] for k in keys}


def place(body, user=None):
    """Where the request is about: a saved field (only the signed-in owner's), an outline, or a point with hectares."""
    if body.get("fieldId") is not None:
        field_id = check_id(body["fieldId"])
        if not user:
            raise ApiError(401, "not_signed_in", "Sign in to use a saved field")
        field = store().field(field_id)
        # Someone else's field gets the same answer as a missing one, so ids reveal nothing.
        if not field or field["userId"] != user["id"]:
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
    pin = pin_of(body, "pin")
    user = store().create_user(text_of(body, "name"), need(body, "role", ("farmer", "manager")),
                               text_of(body, "region"), text_of(body, "village"), pin)
    if not user:
        raise ApiError(409, "name_taken", "This name is already registered")
    return {"token": store().create_session(user["id"]), "user": user}


@api.post("/login")
def login(body: dict, request: Request):
    name, pin, ip = str(need(body, "name")), str(need(body, "pin")), client_ip(request)
    login_limit(name, ip)
    user = store().check_pin(name, pin)
    if not user:
        store().add_failed_login(name, ip)
        raise ApiError(401, "wrong_login", "Wrong name or PIN")
    store().clear_failed_logins(name)
    return {"token": store().create_session(user["id"]), "user": user}


@api.post("/logout")
def logout(authorization: str = Header(None)):
    user_of(authorization)  # 401 if the token is missing, wrong or expired
    store().delete_session(token_of(authorization))
    return {"ok": True}


@api.get("/me")
def me(authorization: str = Header(None)):
    """The signed-in user. A 401 here means the token expired: sign in again."""
    return {"user": user_of(authorization)}


ACCOUNT_KEYS = {"name", "region", "village", "pin", "currentPin"}


@api.patch("/me")
def change_me(body: dict, request: Request, authorization: str = Header(None)):
    """Change name, region, village or PIN. Name and PIN need `currentPin`; the role never changes."""
    user = user_of(authorization)
    if set(body) - ACCOUNT_KEYS:
        raise ApiError(422, "bad_input", f"These cannot be changed: {', '.join(sorted(set(body) - ACCOUNT_KEYS))}")
    changes = {k: text_of(body, k) for k in ("name", "region", "village") if k in body}
    if "pin" in body:
        changes["pin"] = pin_of(body, "pin")
    if not changes:
        raise ApiError(422, "bad_input", "Nothing to change: send name, region, village or pin")
    if "name" in changes or "pin" in changes:
        confirm_pin(user, need(body, "currentPin"), request)
    updated = store().update_user(user["id"], **changes)
    if not updated:
        raise ApiError(409, "name_taken", "This name is already registered")
    if "pin" in changes:  # a new PIN signs out every other device
        store().delete_sessions_of(user["id"], keep=token_of(authorization))
    return {"user": updated}


@api.delete("/me")
def delete_me(body: dict, request: Request, authorization: str = Header(None)):
    """Delete the account and all of its data. Needs `pin`."""
    user = user_of(authorization)
    confirm_pin(user, need(body, "pin"), request)
    store().delete_user(user["id"])
    return {"ok": True}


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
    check = load("snow_check.json")
    return {**found, "shortYears": load("snow.json")["shortYears"], "check": check and check["basins"].get(basin)}


# --- fields

def new_field(body):
    """A field from an outline or a point, with its field check. A fieldId here would copy a saved field."""
    if body.get("fieldId") is not None:
        raise ApiError(422, "bad_input", "Send 'geometry', or 'lat', 'lon' and 'areaHa', not 'fieldId'")
    field = place(body)
    field["fieldCheck"] = engine.field_check(field["site"])
    return field


@api.post("/fields")
def add_field(body: dict, authorization: str = Header(None)):
    user = user_of(authorization, required=False)
    field = new_field(body)
    if user:
        field = {"id": store().save_field(user["id"], field), **field}
    return field


@api.get("/fields")
def list_fields(authorization: str = Header(None)):
    return {"fields": store().fields_of(user_of(authorization)["id"])}


@api.put("/fields/{field_id}")
def change_field(field_id: int, body: dict, authorization: str = Header(None)):
    """Redraw a saved field: same body as POST /fields; height, basin, site and field check are recomputed."""
    user = user_of(authorization)
    check_id(field_id, "field id")
    field = new_field(body)
    if not store().update_field(user["id"], field_id, field):
        raise ApiError(404, "no_field", "This field does not exist")
    return {"id": field_id, **field}


@api.delete("/fields/{field_id}")
def remove_field(field_id: int, authorization: str = Header(None)):
    user = user_of(authorization)
    check_id(field_id, "field id")
    if not store().delete_field(user["id"], field_id):
        raise ApiError(404, "no_field", "This field does not exist")
    return {"ok": True}


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
    view = engine.manager_view(snow_now["anomaly"], source, turns, villages, main_crop, climate)
    return {**view, "mainCrop": main_crop, "basin": basin_id, "snow": without_series(snow_now),
            "evidence": {"rules": engine.RULES, "climate": climate_evidence(climate)}}


@api.get("/manager")
def manager_canal(authorization: str = Header(None)):
    """The canal the signed-in manager saved, or null."""
    return {"canal": store().canal_of(user_of(authorization, "manager")["id"])}


@api.delete("/manager")
def remove_canal(authorization: str = Header(None)):
    """Forget the saved canal. His season message then reaches only his own village."""
    store().delete_canal(user_of(authorization, "manager")["id"])
    return {"ok": True}


@api.post("/manager/message")
def post_message(body: dict, authorization: str = Header(None)):
    user = user_of(authorization, "manager")
    text = str(need(body, "text")).strip()
    if not text or len(text) > MESSAGE_MAX:
        raise ApiError(422, "bad_input", f"'text' must be 1 to {MESSAGE_MAX} characters")
    return store().set_message(user["id"], text)


@api.delete("/manager/message")
def remove_message(authorization: str = Header(None)):
    """Take the season message down; farmers then see no message from him."""
    store().delete_message(user_of(authorization, "manager")["id"])
    return {"ok": True}


@api.get("/message")
def message(village: str):
    return {"message": store().message_for(village)}


# --- farmer

@api.post("/farmer")
def farmer(body: dict, authorization: str = Header(None)):
    user = user_of(authorization, required=False)
    field = place(body, user)
    plan = need(body, "plan", tuple(engine.CROPS))
    rain = rain_at(field["lat"], field["lon"])
    dry = dry_year(field["basin"])
    ctx = {
        "dryAnomaly": dry["anomaly"],
        "areaHa": field["areaHa"],
        "position": need(body, "position", engine.POSITIONS),
        "source": need(body, "source", engine.SOURCES),
        "normalYear": need(body, "normalYear", ("enough", "sometimes", "often", "unknown")),
        "plan": plan,
        "lastCrops": [c for c in body.get("lastCrops", []) if c in engine.CROPS][:2],
        "winterWheatSown": body.get("winterWheatSown") is True,
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
        "dryYear": dry,
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
