"""Changing and deleting through the API, on both stores: account (/me), saved fields, canal and message."""
import pytest
from fastapi.testclient import TestClient

from iseed import main

TALAS = {"lat": 42.52, "lon": 72.3, "areaHa": 2}
SQUARE = {"type": "Polygon", "coordinates": [[[72.30, 42.52], [72.301, 42.52], [72.301, 42.521], [72.30, 42.521], [72.30, 42.52]]]}
ANSWERS = {"position": "end", "source": "gravity", "normalYear": "enough", "plan": "beans", "lastCrops": ["beans"]}
CANAL = {"lat": 42.52, "lon": 72.3, "source": "gravity", "normalTurns": 6, "villages": [{"name": "Kök-Say", "ha": 120}]}


@pytest.fixture
def api(store, monkeypatch):
    monkeypatch.setattr(main, "store", lambda: store)
    monkeypatch.delenv("VERCEL", raising=False)
    return TestClient(main.app)


def sign_up(api, name, role="farmer", village="Kök-Say", pin="1234"):
    res = api.post("/register", json={"name": name, "role": role, "region": "Talas", "village": village, "pin": pin})
    assert res.status_code == 200, res.json()
    return {"Authorization": "Bearer " + res.json()["token"]}


def code(res):
    return res.status_code, res.json().get("code")


# ---------------------------------------------------------------- account


def test_me(api):
    auth = sign_up(api, "Aibek")
    assert api.get("/me", headers=auth).json()["user"]["name"] == "Aibek"
    assert code(api.get("/me")) == (401, "not_signed_in")


def test_change_village_and_region_without_pin(api):
    auth = sign_up(api, "Aibek")
    res = api.patch("/me", json={"village": "Ak-Suu", "region": "Chüy"}, headers=auth)
    assert res.json()["user"] == {**res.json()["user"], "village": "Ak-Suu", "region": "Chüy"}
    assert api.get("/me", headers=auth).json()["user"]["village"] == "Ak-Suu"


def test_village_change_moves_the_season_message(api):
    boss = sign_up(api, "Mirab", role="manager", village="Talas")
    api.post("/manager/message", json={"text": "Turns start 20 April"}, headers=boss)
    farmer = sign_up(api, "Aibek", village="Elsewhere")
    assert api.post("/farmer", json={**TALAS, **ANSWERS}, headers=farmer).json()["message"] is None
    api.patch("/me", json={"village": "talas"}, headers=farmer)
    assert api.post("/farmer", json={**TALAS, **ANSWERS}, headers=farmer).json()["message"]["manager"] == "Mirab"


def test_name_and_pin_need_the_current_pin(api):
    auth = sign_up(api, "Aibek")
    assert code(api.patch("/me", json={"name": "Aibek K."}, headers=auth)) == (422, "bad_input")
    assert code(api.patch("/me", json={"pin": "9876", "currentPin": "0000"}, headers=auth)) == (403, "wrong_pin")
    assert api.patch("/me", json={"name": "Aibek K.", "currentPin": "1234"}, headers=auth).json()["user"]["name"] == "Aibek K."
    assert api.post("/login", json={"name": "Aibek K.", "pin": "1234"}).status_code == 200


def test_new_pin_signs_out_other_devices(api):
    phone = sign_up(api, "Aibek")
    laptop = {"Authorization": "Bearer " + api.post("/login", json={"name": "Aibek", "pin": "1234"}).json()["token"]}
    assert api.patch("/me", json={"pin": "9876", "currentPin": "1234"}, headers=phone).status_code == 200
    assert api.get("/me", headers=phone).status_code == 200   # the device that changed it stays in
    assert code(api.get("/me", headers=laptop)) == (401, "not_signed_in")
    assert api.post("/login", json={"name": "Aibek", "pin": "1234"}).status_code == 401
    assert api.post("/login", json={"name": "Aibek", "pin": "9876"}).status_code == 200


def test_wrong_current_pin_counts_toward_the_login_limit(api):
    auth = sign_up(api, "Aibek")
    for guess in ("0000", "1111", "2222", "3333", "4444"):
        assert code(api.patch("/me", json={"pin": "9999", "currentPin": guess}, headers=auth)) == (403, "wrong_pin")
    assert code(api.patch("/me", json={"pin": "9999", "currentPin": "1234"}, headers=auth)) == (429, "too_many_tries")
    assert code(api.post("/login", json={"name": "Aibek", "pin": "1234"})) == (429, "too_many_tries")


@pytest.mark.parametrize("body", [{"role": "manager"}, {"id": 5}, {}, {"village": "   "}, {"village": 7},
                                  {"pin": "12", "currentPin": "1234"}])
def test_bad_changes_are_refused(api, body):
    auth = sign_up(api, "Aibek")
    assert code(api.patch("/me", json=body, headers=auth)) == (422, "bad_input")
    assert api.get("/me", headers=auth).json()["user"]["role"] == "farmer"


def test_rename_to_a_taken_name(api):
    auth = sign_up(api, "Aibek")
    sign_up(api, "Bakyt")
    assert code(api.patch("/me", json={"name": "Bakyt", "currentPin": "1234"}, headers=auth)) == (409, "name_taken")


def test_register_refuses_blank_text(api):
    res = api.post("/register", json={"name": "   ", "role": "farmer", "region": "Talas", "village": "X", "pin": "1234"})
    assert code(res) == (422, "bad_input")


def test_delete_account(api):
    boss = sign_up(api, "Mirab", role="manager", village="Talas")
    api.post("/manager", json=CANAL, headers=boss)
    api.post("/manager/message", json={"text": "Hello"}, headers=boss)
    api.post("/fields", json=TALAS, headers=boss)
    assert code(api.request("DELETE", "/me", json={"pin": "0000"}, headers=boss)) == (403, "wrong_pin")
    assert code(api.request("DELETE", "/me", json={}, headers=boss)) == (422, "bad_input")
    assert api.request("DELETE", "/me", json={"pin": "1234"}, headers=boss).json() == {"ok": True}
    assert code(api.get("/me", headers=boss)) == (401, "not_signed_in")
    assert api.get("/message", params={"village": "Kök-Say"}).json()["message"] is None
    sign_up(api, "Mirab")  # the name can be registered again


# ---------------------------------------------------------------- saved fields


def test_redraw_a_saved_field(api):
    auth = sign_up(api, "Aibek")
    field = api.post("/fields", json=TALAS, headers=auth).json()
    redrawn = api.put(f"/fields/{field['id']}", json={"geometry": SQUARE}, headers=auth).json()
    assert redrawn["id"] == field["id"] and 0.8 < redrawn["areaHa"] < 1.0 and redrawn["geometry"] == SQUARE
    assert redrawn["fieldCheck"]["verdict"] in ("good", "careful", "no")
    assert api.get("/fields", headers=auth).json()["fields"] == [redrawn]
    farmer = api.post("/farmer", json={"fieldId": field["id"], **ANSWERS}, headers=auth).json()
    assert farmer["field"]["areaHa"] == redrawn["areaHa"]


def test_delete_a_saved_field(api):
    auth = sign_up(api, "Aibek")
    keep, drop = (api.post("/fields", json=TALAS, headers=auth).json()["id"] for _ in range(2))
    assert api.delete(f"/fields/{drop}", headers=auth).json() == {"ok": True}
    assert [f["id"] for f in api.get("/fields", headers=auth).json()["fields"]] == [keep]
    assert code(api.delete(f"/fields/{drop}", headers=auth)) == (404, "no_field")


def test_fields_of_others_cannot_be_changed_or_deleted(api):
    aibek, bakyt = sign_up(api, "Aibek"), sign_up(api, "Bakyt")
    field_id = api.post("/fields", json=TALAS, headers=aibek).json()["id"]
    assert code(api.put(f"/fields/{field_id}", json={"geometry": SQUARE}, headers=bakyt)) == (404, "no_field")
    assert code(api.delete(f"/fields/{field_id}", headers=bakyt)) == (404, "no_field")
    assert code(api.delete(f"/fields/{field_id}")) == (401, "not_signed_in")
    assert api.get("/fields", headers=aibek).json()["fields"][0]["areaHa"] == 2


@pytest.mark.parametrize("path", ["/fields/abc", "/fields/-1", "/fields/0", "/fields/99999999999999999999"])
def test_bad_field_ids_are_bad_input(api, path):
    auth = sign_up(api, "Aibek")
    assert code(api.delete(path, headers=auth)) == (422, "bad_input")


def test_put_refuses_bad_bodies(api):
    auth = sign_up(api, "Aibek")
    field_id = api.post("/fields", json=TALAS, headers=auth).json()["id"]
    assert code(api.put(f"/fields/{field_id}", json={"fieldId": field_id}, headers=auth)) == (422, "bad_input")
    assert code(api.put(f"/fields/{field_id}", json={"lat": 42.5}, headers=auth)) == (422, "bad_input")
    assert code(api.put(f"/fields/{field_id}", content="not json", headers=auth)) == (422, "bad_input")


# ---------------------------------------------------------------- canal and season message


def test_manager_deletes_canal_and_message(api):
    boss = sign_up(api, "Mirab", role="manager", village="Talas")
    farmer = sign_up(api, "Aibek")
    api.post("/manager", json=CANAL, headers=boss)
    api.post("/manager/message", json={"text": "Hello"}, headers=boss)
    assert code(api.delete("/manager", headers=farmer)) == (403, "wrong_role")
    assert code(api.delete("/manager/message", headers=farmer)) == (403, "wrong_role")
    assert api.delete("/manager", headers=boss).json() == {"ok": True}
    assert api.get("/manager", headers=boss).json()["canal"] is None
    assert api.get("/message", params={"village": "Kök-Say"}).json()["message"] is None  # canal village gone
    assert api.get("/message", params={"village": "Talas"}).json()["message"]["text"] == "Hello"
    assert api.delete("/manager/message", headers=boss).json() == {"ok": True}
    assert api.get("/message", params={"village": "Talas"}).json()["message"] is None
    assert api.delete("/manager/message", headers=boss).json() == {"ok": True}  # nothing left: still fine
