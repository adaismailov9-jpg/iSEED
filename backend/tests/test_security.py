"""Security of the API, on both stores: saved fields belong to their owner, sessions expire and can
be ended, and /login stops PIN guessing."""
import pytest
from fastapi.testclient import TestClient

from iseed import main

TALAS = {"lat": 42.52, "lon": 72.3, "areaHa": 2}
ANSWERS = {"position": "end", "source": "gravity", "normalYear": "enough", "plan": "beans", "lastCrops": ["beans"]}


@pytest.fixture
def api(store, monkeypatch):
    monkeypatch.setattr(main, "store", lambda: store)
    monkeypatch.delenv("VERCEL", raising=False)
    return TestClient(main.app)


def sign_up(api, name, pin="1234", role="farmer"):
    res = api.post("/register", json={"name": name, "role": role, "region": "Talas", "village": "Kök-Say", "pin": pin})
    assert res.status_code == 200
    return {"Authorization": "Bearer " + res.json()["token"]}


def login(api, name, pin, ip=None):
    headers = {"X-Forwarded-For": ip} if ip else {}
    return api.post("/login", json={"name": name, "pin": pin}, headers=headers)


# ---------------------------------------------------------------- saved fields belong to their owner


def test_saved_field_needs_sign_in_and_the_owner(api):
    aibek, bakyt = sign_up(api, "Aibek"), sign_up(api, "Bakyt")
    field_id = api.post("/fields", json=TALAS, headers=aibek).json()["id"]
    body = {"fieldId": field_id, **ANSWERS}

    assert api.post("/farmer", json=body, headers=aibek).status_code == 200
    stranger = api.post("/farmer", json=body, headers=bakyt)
    assert (stranger.status_code, stranger.json()["code"]) == (404, "no_field")
    missing = api.post("/farmer", json={**body, "fieldId": 999}, headers=bakyt)
    assert stranger.json() == missing.json()  # someone else's field looks exactly like no field
    anonymous = api.post("/farmer", json=body)
    assert (anonymous.status_code, anonymous.json()["code"]) == (401, "not_signed_in")


def test_post_fields_cannot_copy_a_saved_field(api):
    aibek, bakyt = sign_up(api, "Aibek"), sign_up(api, "Bakyt")
    field_id = api.post("/fields", json=TALAS, headers=aibek).json()["id"]
    for who in (bakyt, aibek):
        res = api.post("/fields", json={"fieldId": field_id}, headers=who)
        assert (res.status_code, res.json()["code"]) == (422, "bad_input")
    assert api.get("/fields", headers=bakyt).json()["fields"] == []
    assert len(api.get("/fields", headers=aibek).json()["fields"]) == 1


@pytest.mark.parametrize("bad", ["1", "abc", 1.5, True, [1]])
def test_field_id_must_be_a_whole_number(api, bad):
    aibek = sign_up(api, "Aibek")
    res = api.post("/farmer", json={"fieldId": bad, **ANSWERS}, headers=aibek)
    assert (res.status_code, res.json()["code"]) == (422, "bad_input")


# ---------------------------------------------------------------- sessions


def test_logout_ends_that_session_only(api):
    first = sign_up(api, "Aibek")
    second = {"Authorization": "Bearer " + login(api, "Aibek", "1234").json()["token"]}
    assert api.post("/logout", headers=first).json() == {"ok": True}
    assert api.get("/fields", headers=first).status_code == 401
    assert api.post("/logout", headers=first).status_code == 401  # already signed out
    assert api.get("/fields", headers=second).status_code == 200
    assert api.post("/logout").status_code == 401


def test_session_expires_after_30_days(api, clock):
    auth = sign_up(api, "Aibek")
    clock.forward(days=29)
    assert api.get("/fields", headers=auth).status_code == 200
    clock.forward(days=2)
    res = api.get("/fields", headers=auth)
    assert (res.status_code, res.json()["code"]) == (401, "not_signed_in")


# ---------------------------------------------------------------- PIN guessing


def test_five_wrong_pins_lock_that_name_for_15_minutes(api, clock):
    sign_up(api, "Aibek", pin="1234")
    sign_up(api, "Bakyt", pin="5555")
    for guess in ("0000", "1111", "2222", "3333", "4444"):
        assert login(api, "Aibek", guess).status_code == 401
    locked = login(api, "Aibek", "1234")  # even the right PIN is refused while locked
    assert (locked.status_code, locked.json()["code"]) == (429, "too_many_tries")
    assert login(api, "Bakyt", "5555").status_code == 200  # other names are not affected
    clock.forward(minutes=16)
    assert login(api, "Aibek", "1234").status_code == 200


def test_a_successful_login_resets_the_count(api):
    sign_up(api, "Aibek")
    for _ in range(4):
        login(api, "Aibek", "0000")
    assert login(api, "Aibek", "1234").status_code == 200
    for _ in range(4):
        assert login(api, "Aibek", "0000").status_code == 401  # a fresh count: not locked yet


def test_twenty_wrong_pins_from_one_address_block_that_address(api):
    sign_up(api, "Aibek")
    for i in range(20):
        assert login(api, f"guess-{i}", "1234").status_code == 401  # spraying names, 1 try each
    res = login(api, "Aibek", "1234")
    assert (res.status_code, res.json()["code"]) == (429, "too_many_tries")


def test_a_faked_forwarded_for_header_does_not_reset_the_limit(api):
    """Off Vercel, X-Forwarded-For is ignored: a client cannot pose as a new address on every try."""
    sign_up(api, "Aibek")
    for i in range(20):
        login(api, f"guess-{i}", "1234", ip=f"10.0.0.{i}")
    assert login(api, "Aibek", "1234", ip="10.9.9.9").status_code == 429


def test_on_vercel_the_platform_address_is_used(api, monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    sign_up(api, "Aibek")
    for i in range(20):
        login(api, f"guess-{i}", "1234", ip="203.0.113.7")
    assert login(api, "Aibek", "1234", ip="203.0.113.7").status_code == 429
    assert login(api, "Aibek", "1234", ip="198.51.100.2").status_code == 200  # another farmer's address
