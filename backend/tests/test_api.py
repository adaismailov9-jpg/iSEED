"""The API end to end, on the committed NASA data files and a throwaway database."""
import pytest
from fastapi.testclient import TestClient

from iseed import main

TALAS = {"lat": 42.52, "lon": 72.3, "areaHa": 2}
ANSWERS = {"position": "end", "source": "gravity", "normalYear": "enough", "plan": "beans", "lastCrops": ["beans", "wheat"]}
SQUARE = {"type": "Polygon", "coordinates": [[[72.30, 42.52], [72.301, 42.52], [72.301, 42.521], [72.30, 42.521], [72.30, 42.52]]]}


@pytest.fixture
def api(store, monkeypatch):
    """`store` (tests/conftest.py) is a fresh SQLiteStore or PostgresStore: every test runs on both."""
    monkeypatch.setattr(main, "store", lambda: store)
    return TestClient(main.app)


def sign_up(api, name, role, village="Kök-Say"):
    res = api.post("/register", json={"name": name, "role": role, "region": "Talas", "village": village, "pin": "1234"})
    assert res.status_code == 200
    return {"Authorization": "Bearer " + res.json()["token"]}


def test_register_login_and_wrong_pin(api):
    sign_up(api, "Aibek", "farmer")
    assert api.post("/register", json={"name": "Aibek", "role": "farmer", "region": "Talas", "village": "X", "pin": "1234"}).json()["code"] == "name_taken"
    assert api.post("/login", json={"name": "Aibek", "pin": "1234"}).json()["user"]["role"] == "farmer"
    assert api.post("/login", json={"name": "Aibek", "pin": "0000"}).status_code == 401
    assert api.post("/register", json={"name": "B", "role": "farmer", "region": "Talas", "village": "X", "pin": "12"}).status_code == 422


def test_field_outline_gets_area_basin_height_and_is_saved(api):
    auth = sign_up(api, "Aibek", "farmer")
    field = api.post("/fields", json={"geometry": SQUARE}, headers=auth).json()
    assert 0.8 < field["areaHa"] < 1.0 and field["basin"] == "talas"
    assert 800 < field["elevM"] < 2500 and field["fieldCheck"]["verdict"] in ("good", "careful", "no")
    assert [f["id"] for f in api.get("/fields", headers=auth).json()["fields"]] == [field["id"]]
    assert api.get("/fields").status_code == 401


def test_farmer_result_from_saved_field_matches_inline(api):
    auth = sign_up(api, "Aibek", "farmer")
    field = api.post("/fields", json=TALAS, headers=auth).json()
    saved = api.post("/farmer", json={"fieldId": field["id"], **ANSWERS}, headers=auth).json()
    inline = api.post("/api/farmer", json={**TALAS, **ANSWERS}).json()
    assert saved["options"] == inline["options"] and saved["options"][0]["crop"] == "beans"
    assert saved["snow"]["basin"] == "talas" and saved["fieldCheck"]["checks"]


def test_manager_message_reaches_farmers_in_his_villages(api):
    boss = sign_up(api, "Mirab", "manager", village="Talas")
    farmer = sign_up(api, "Aibek", "farmer", village="kök-say ")
    other = sign_up(api, "Bakyt", "farmer", village="Elsewhere")
    canal = {"lat": 42.52, "lon": 72.3, "source": "gravity", "normalTurns": 6, "villages": [{"name": "Kök-Say", "ha": 120}]}
    view = api.post("/manager", json=canal, headers=boss).json()
    assert view["basin"] == "talas" and view["totalHa"] == 120 and len(view["positions"]) == 3
    assert api.post("/manager/message", json={"text": "x" * 281}, headers=boss).status_code == 422
    assert api.post("/manager/message", json={"text": "Water turns start 20 April"}, headers=farmer).status_code == 403
    api.post("/manager/message", json={"text": "Water turns start 20 April"}, headers=boss)
    assert api.post("/farmer", json={**TALAS, **ANSWERS}, headers=farmer).json()["message"]["text"] == "Water turns start 20 April"
    assert api.post("/farmer", json={**TALAS, **ANSWERS}, headers=other).json()["message"] is None
    assert api.get("/message", params={"village": "Kök-Say"}).json()["message"]["manager"] == "Mirab"


def test_errors_are_code_and_message(api):
    assert api.post("/farmer", json={"lat": 42.5}).json()["code"] == "bad_input"
    assert api.get("/basin", params={"lat": 43.24, "lon": 76.9}).json()["code"] == "no_basin"  # Almaty


def test_wrong_types_get_422_not_500(api):
    canal = {"lat": 42.52, "lon": 72.3, "source": "gravity", "normalTurns": 6, "villages": [{"name": "Kök-Say", "ha": 120}]}
    bad = [
        ("/fields", {"lat": "42.5", "lon": 72.3, "areaHa": 1}),
        ("/fields", {"lat": 999, "lon": 72.3, "areaHa": 1}),
        ("/fields", {"geometry": {"type": "Polygon", "coordinates": [[["a", "b"], ["c", "d"], ["e", "f"], ["a", "b"]]]}}),
        ("/farmer", {"lat": True, "lon": 72.3, "areaHa": 1, **ANSWERS}),
        ("/manager", {**canal, "villages": "abc"}),
        ("/manager", {**canal, "villages": [1]}),
        ("/manager", {**canal, "normalTurns": "6"}),
        ("/manager", {**canal, "lat": "42"}),
    ]
    for path, body in bad:
        res = api.post(path, json=body)
        assert res.status_code in (404, 422), (path, body, res.status_code)


def test_farmer_outside_the_basins_is_no_basin(api):
    """No snow signal there, so no options (the result screen needs snow)."""
    res = api.post("/farmer", json={"lat": 43.5, "lon": 76.9, "areaHa": 1, **ANSWERS})
    assert res.status_code == 404 and res.json()["code"] == "no_basin"
