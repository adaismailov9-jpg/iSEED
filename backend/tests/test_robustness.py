"""Garbage in, never a 500 out; claims the data cannot back up are not made; a stranger cannot pose as a manager.

Every test runs on both stores (SQLite, PostgreSQL): some bad input only breaks one of them
(PostgreSQL refuses a NUL character in text, SQLite does not).
"""
import copy
import json

import pytest
from fastapi.testclient import TestClient

from iseed import engine, main

FARM = {"lat": 42.52, "lon": 72.3, "areaHa": 2, "position": "end", "source": "gravity", "normalYear": "enough",
        "plan": "beans", "lastCrops": ["beans"], "winterWheatSown": False, "soil": "clay", "elevM": 1200}
CANAL = {"lat": 42.52, "lon": 72.3, "source": "gravity", "normalTurns": 6, "mainCrop": "beans",
         "villages": [{"name": "Kök-Say", "ha": 10}], "elevM": 1200}
# Values a client (or an attacker) might put in any field.
JUNK = [None, "", " ", "x", "\x00", 0, -1, 10**30, 1e308, True, [], {}, ["a"], {"a": 1}, "A" * 5000,
        float("inf"), float("nan")]


@pytest.fixture
def api(store, monkeypatch):
    monkeypatch.setattr(main, "store", lambda: store)
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("MANAGER_INVITE_CODE", raising=False)
    return TestClient(main.app, raise_server_exceptions=False)


def sign_up(api, name, role="farmer", village="Kök-Say", **extra):
    res = api.post("/register", json={"name": name, "role": role, "region": "Talas", "village": village, "pin": "1234", **extra})
    assert res.status_code == 200, res.text
    return {"Authorization": "Bearer " + res.json()["token"]}


def send(api, method, path, body, headers=None):
    """Raw JSON, so NaN and Infinity go out as the literals NaN and Infinity, as in a hand-made request."""
    return api.request(method, path, content=json.dumps(body, allow_nan=True),
                       headers={"Content-Type": "application/json", **(headers or {})})


def fuzz(api, method, path, body, headers=None):
    """Put every junk value into every field (and an unknown one): nothing may answer 5xx."""
    failures = []
    for key in [*body, "extra"]:
        for junk in JUNK:
            bad = copy.deepcopy(body)
            bad[key] = junk
            res = send(api, method, path, bad, headers)
            if res.status_code >= 500:
                failures.append(f"{key}={junk!r:.30} -> {res.status_code}")
            else:
                assert "code" in res.json() or res.status_code == 200, (key, junk, res.text)
    assert not failures, failures


# ---------------------------------------------------------------- no 500 from bad input

def test_farmer_survives_junk_in_every_field(api):
    fuzz(api, "POST", "/farmer", FARM)


def test_new_field_survives_junk_in_every_field(api):
    auth = sign_up(api, "Aibek")
    point = {"lat": 42.52, "lon": 72.3, "areaHa": 2, "elevM": 1200}
    fuzz(api, "POST", "/fields", point, auth)
    field = api.post("/fields", json=point, headers=auth).json()
    fuzz(api, "PUT", f"/fields/{field['id']}", point, auth)


def test_manager_survives_junk_in_every_field(api):
    fuzz(api, "POST", "/manager", CANAL, sign_up(api, "Mirab", "manager"))


def test_message_and_account_survive_junk(api):
    boss = sign_up(api, "Mirab", "manager")
    fuzz(api, "POST", "/manager/message", {"text": "Turns start 20 April"}, boss)
    fuzz(api, "PATCH", "/me", {"village": "Talas", "region": "Talas"}, sign_up(api, "Aibek"))


def test_register_and_login_survive_junk(api):
    sign_up(api, "Aibek")
    fuzz(api, "POST", "/register", {"name": "New", "role": "farmer", "region": "Talas", "village": "V", "pin": "1234"})
    fuzz(api, "POST", "/login", {"name": "Aibek", "pin": "1234"})


def test_the_numbers_that_used_to_crash_the_engine_are_refused(api):
    """NaN, Infinity and 1e308 are valid in Python's JSON and passed `area > 0`; they then crashed the engine (500)."""
    for lit in ("NaN", "Infinity", "-Infinity", "1e308"):
        for key, value in (("areaHa", 2), ("elevM", 1200)):
            raw = json.dumps(FARM).replace(f'"{key}": {value}', f'"{key}": {lit}')
            res = api.post("/farmer", content=raw, headers={"Content-Type": "application/json"})
            assert res.status_code == 422 and res.json()["code"] == "bad_input", (key, lit, res.text)
    raw = json.dumps(CANAL).replace('"ha": 10', '"ha": Infinity')
    assert api.post("/manager", content=raw, headers={"Content-Type": "application/json"}).status_code == 422


def test_last_crops_null_is_none_and_the_rest_must_be_a_list(api):
    assert api.post("/farmer", json={**FARM, "lastCrops": None}).status_code == 200  # null from a form: no crops
    assert api.post("/farmer", json={**FARM, "lastCrops": []}).status_code == 200
    for bad in (5, "beans", {"a": 1}, [1, 2]):
        assert api.post("/farmer", json={**FARM, "lastCrops": bad}).status_code == 422, bad


def test_unknown_crop_in_a_list_is_dropped_not_refused(api):
    res = api.post("/farmer", json={**FARM, "lastCrops": ["beans", "moonrock"]})
    assert res.status_code == 200 and res.json()["input"]["lastCrops"] == ["beans"]


def test_limits(api):
    big = {"type": "Polygon", "coordinates": [[[70, 39], [80, 39], [80, 43], [70, 43], [70, 39]]]}  # ~37 million ha
    assert api.post("/fields", json={"geometry": big}).status_code == 422
    assert api.post("/fields", json={"lat": 42.5, "lon": 72.3, "areaHa": 10_001}).status_code == 422
    assert api.post("/fields", json={"lat": 42.5, "lon": 72.3, "areaHa": 10_000}).status_code == 200
    reg = {"name": "x" * 81, "role": "farmer", "region": "T", "village": "V", "pin": "1234"}
    assert api.post("/register", json=reg).status_code == 422
    assert api.post("/register", json={**reg, "name": "x" * 80}).status_code == 200
    assert api.post("/register", json={**reg, "name": "Arab", "pin": "١٢٣٤"}).status_code == 422  # Arabic-Indic digits
    assert api.post("/register", json={**reg, "name": "Nul\x00"}).status_code < 500  # PostgreSQL cannot store NUL


def test_elevation_zero_is_a_height_not_a_missing_value(api):
    res = api.post("/farmer", json={**FARM, "elevM": 0}).json()
    assert res["field"]["elevM"] == 0  # `0 or site` used to swap the farmer's sea-level answer for the grid's


def test_an_unexpected_bug_still_answers_json(api, monkeypatch):
    def boom(_):
        raise RuntimeError("bug")
    monkeypatch.setattr(engine, "farmer_options", boom)
    res = api.post("/farmer", json=FARM)
    assert res.status_code == 500 and res.json()["code"] == "server_error" and "bug" not in res.text  # no internals leaked


# ---------------------------------------------------------------- claims the data cannot back up

def option(price_known, dry_low=100):
    return {"priceKnown": price_known, "dry": {"income": {"low": dry_low} if price_known else None}}


def test_plan_earns_most_needs_every_price_to_be_known():
    plan = option(True, 100)
    assert engine.plan_earns_most([plan, option(True, 50)]) is True
    assert engine.plan_earns_most([plan, option(True, 50), option(True, 150)]) is False
    assert engine.plan_earns_most([plan, option(False)]) is None  # was True: unknown income counted as -1
    assert engine.plan_earns_most([option(False), option(True)]) is None  # the plan has no price
    assert engine.plan_earns_most([plan]) is None  # nothing to compare with


def test_plan_earns_most_is_never_true_when_a_rival_has_no_price(api):
    """With beans, potato and sugar beet as the plan, the answer used to be True against unpriced alfalfa."""
    for plan in engine.CROPS:
        res = api.post("/farmer", json={**FARM, "plan": plan, "lastCrops": []}).json()
        if res["planEarnsMost"] is not None:
            assert all(o["priceKnown"] for o in res["options"]), (plan, res["options"])


# ---------------------------------------------------------------- nobody can pose as a water manager

def message_seen_by_village(api, village="Kök-Say"):
    return api.get("/message", params={"village": village}).json()["message"]


def test_without_an_invite_code_anyone_can_be_a_manager_as_before(api):
    """The default (local work, tests): MANAGER_INVITE_CODE is not set."""
    sign_up(api, "Anyone", "manager")


def test_a_stranger_cannot_replace_the_real_managers_message(api, monkeypatch):
    monkeypatch.setenv("MANAGER_INVITE_CODE", "canal-2026")
    real = sign_up(api, "Mirab-Aga", "manager", inviteCode="canal-2026")
    api.post("/manager/message", json={"text": "Water turns start 20 April"}, headers=real)
    fake = {"name": "mirab-aga", "role": "manager", "region": "x", "village": "kök-say", "pin": "1234"}
    for body in (fake, {**fake, "inviteCode": "wrong"}, {**fake, "inviteCode": 123}, {**fake, "inviteCode": None}):
        res = api.post("/register", json=body)
        assert res.status_code == 403 and res.json()["code"] == "wrong_invite", body
    assert message_seen_by_village(api)["text"] == "Water turns start 20 April"


def test_farmers_do_not_need_the_code_and_the_code_is_not_logged_in_the_answer(api, monkeypatch):
    monkeypatch.setenv("MANAGER_INVITE_CODE", "canal-2026")
    sign_up(api, "Aibek")  # a farmer: no code
    res = api.post("/register", json={"name": "Boss", "role": "manager", "region": "x", "village": "y", "pin": "1234",
                                      "inviteCode": "canal-2026"})
    assert res.status_code == 200 and "canal-2026" not in res.text


def test_guessing_the_invite_code_is_limited_per_address(api, monkeypatch):
    monkeypatch.setenv("MANAGER_INVITE_CODE", "canal-2026")
    body = {"name": "Guess", "role": "manager", "region": "x", "village": "y", "pin": "1234"}
    codes = [api.post("/register", json={**body, "inviteCode": f"try-{i}"}).status_code for i in range(7)]
    assert codes == [403] * 5 + [429] * 2  # the same limit as wrong PINs: 5 per name-key
    other = api.post("/register", json={**body, "inviteCode": "canal-2026"}, headers={"X-Forwarded-For": "9.9.9.9"})
    assert other.status_code == 429  # off Vercel the header is ignored, so this is still the same address


# ---------------------------------------------------------------- /health tells when the database is not usable

def test_health_reports_a_readable_database(api):
    assert api.get("/health").json()["db"] is True


def test_health_reports_an_unreadable_database_without_failing(api, monkeypatch):
    class Broken:
        def ready(self):
            raise RuntimeError("relation \"users\" does not exist")

    monkeypatch.setattr(main, "store", lambda: Broken())
    res = api.get("/health")
    assert res.status_code == 200 and res.json()["db"] is False and "relation" not in res.text


# ---------------------------------------------------------------- what is stored

def test_only_the_checked_outline_is_stored(api):
    """The outline used to be saved as the client sent it: extra keys, NUL characters (a 500 on PostgreSQL), any size."""
    auth = sign_up(api, "Aibek")
    outline = [[72.30, 42.52], [72.301, 42.52], [72.301, 42.521], [72.30, 42.521]]
    geometry = {"type": "Polygon", "coordinates": [outline], "junk": "\x00" * 10, "big": "x" * 200_000}
    res = api.post("/fields", json={"geometry": geometry}, headers=auth)
    assert res.status_code == 200 and set(res.json()["geometry"]) == {"type", "coordinates"}
    stored = api.get("/fields", headers=auth).json()["fields"][0]["geometry"]
    assert set(stored) == {"type", "coordinates"} and stored["coordinates"][0][0] == stored["coordinates"][0][-1]  # closed ring
    assert len(stored["coordinates"][0]) == 5
