"""Side by side: the same API calls on SQLiteStore and on PostgresStore must give the same answers.

The scenario touches every route that reads or writes the store, plus the error paths. Status
codes and JSON bodies are compared call by call; only session tokens (random) are masked.

Known, intended difference (covered in test_store.py): Postgres uses up an id on a rejected
"name taken" sign-up, so ids may skip. The scenario therefore tries the duplicate name last.
"""
import pytest
from fastapi.testclient import TestClient

from iseed import main
from iseed.storage import SQLiteStore

SQUARE = {"type": "Polygon", "coordinates": [[[72.30, 42.52], [72.301, 42.52], [72.301, 42.521], [72.30, 42.521], [72.30, 42.52]]]}
TALAS = {"lat": 42.52, "lon": 72.3, "areaHa": 2}
ANSWERS = {"position": "end", "source": "gravity", "normalYear": "enough", "plan": "beans", "lastCrops": ["beans", "wheat"]}
CANAL = {"lat": 42.52, "lon": 72.3, "source": "gravity", "normalTurns": 6, "mainCrop": "beans",
         "villages": [{"name": "Kök-Say", "ha": 120}, {"name": "Ak-Bulak", "ha": 80}]}


def mask_tokens(body):
    if isinstance(body, dict):
        return {k: "<token>" if k == "token" else mask_tokens(v) for k, v in body.items()}
    if isinstance(body, list):
        return [mask_tokens(v) for v in body]
    return body


def scenario(store, monkeypatch):
    """Run the calls; return [(step, status, body)]."""
    monkeypatch.setattr(main, "store", lambda: store)
    api = TestClient(main.app)
    steps, tokens = [], {}

    def call(step, method, path, who=None, **kwargs):
        headers = kwargs.pop("headers", {})
        if who:
            headers["Authorization"] = "Bearer " + tokens[who]
        res = api.request(method, path, headers=headers, **kwargs)
        body = res.json()
        if step.startswith("register ") and res.status_code == 200:
            tokens[step.split()[1]] = body["token"]
        steps.append((step, res.status_code, mask_tokens(body)))
        return body

    # accounts
    call("register boss", "POST", "/register", json={"name": "Mirab", "role": "manager", "region": "Talas", "village": "Talas", "pin": "4321"})
    call("register aibek", "POST", "/register", json={"name": " Aibek ", "role": "farmer", "region": "Talas", "village": "kök-say ", "pin": "1234"})
    call("register bakyt", "POST", "/register", json={"name": "Bakyt", "role": "farmer", "region": "Talas", "village": "Elsewhere", "pin": "1111"})
    call("register asan (Ak-Bulak)", "POST", "/register", json={"name": "Asan", "role": "farmer", "region": "Talas", "village": "AK-BULAK", "pin": "2222"})
    call("bad pin format", "POST", "/register", json={"name": "C", "role": "farmer", "region": "Talas", "village": "X", "pin": "12"})
    call("bad role", "POST", "/register", json={"name": "D", "role": "admin", "region": "Talas", "village": "X", "pin": "1234"})
    call("login ok", "POST", "/login", json={"name": "Aibek", "pin": "1234"})
    call("login wrong pin", "POST", "/login", json={"name": "Aibek", "pin": "0000"})
    call("login unknown", "POST", "/login", json={"name": "Nobody", "pin": "1234"})

    # fields
    first = call("field from outline", "POST", "/fields", "aibek", json={"geometry": SQUARE})
    call("field from point", "POST", "/fields", "aibek", json=TALAS)
    call("field not signed in (not saved)", "POST", "/fields", json=TALAS)
    call("my fields", "GET", "/fields", "aibek")
    call("other farmer sees none", "GET", "/fields", "bakyt")
    call("fields not signed in", "GET", "/fields")
    call("fields bad token", "GET", "/fields", headers={"Authorization": "Bearer nope"})

    # manager: canal and season message
    call("no canal yet", "GET", "/manager", "boss")
    call("save canal", "POST", "/manager", "boss", json=CANAL)
    call("save canal again (replaces)", "POST", "/manager", "boss", json={**CANAL, "normalTurns": 5})
    call("read canal", "GET", "/manager", "boss")
    call("farmer cannot read canal", "GET", "/manager", "aibek")
    call("no message yet", "GET", "/message", params={"village": "Kök-Say"})
    call("post message", "POST", "/manager/message", "boss", json={"text": "  Old text  "})
    call("post message again (replaces)", "POST", "/manager/message", "boss", json={"text": "Water turns start 20 April"})
    call("message too long", "POST", "/manager/message", "boss", json={"text": "x" * 281})
    call("farmer cannot post", "POST", "/manager/message", "aibek", json={"text": "hi"})
    for village in ("Kök-Say", " kök-say", "Ak-Bulak", "talas", "Elsewhere"):
        call(f"message for {village!r}", "GET", "/message", params={"village": village})

    # farmer results: saved field vs inline, with and without a message
    call("farmer on saved field", "POST", "/farmer", "aibek", json={"fieldId": first["id"], **ANSWERS})
    call("farmer inline, canal village", "POST", "/farmer", "asan", json={**TALAS, **ANSWERS})
    call("farmer inline, no manager", "POST", "/farmer", "bakyt", json={**TALAS, **ANSWERS})
    call("farmer not signed in", "POST", "/farmer", json={**TALAS, **ANSWERS})
    call("farmer unknown field", "POST", "/farmer", "aibek", json={"fieldId": 999, **ANSWERS})

    # routes that do not touch the store, for completeness
    call("basin", "GET", "/basin", params={"lat": 42.52, "lon": 72.3})
    call("snow", "GET", "/snow", params={"basin": "talas"})
    call("crops", "GET", "/crops")

    # last, because a rejected sign-up uses up an id in Postgres (ids may skip; see module docstring)
    call("name taken", "POST", "/register", json={"name": "Aibek", "role": "manager", "region": "Chüy", "village": "X", "pin": "9999"})
    return steps


def test_sqlite_and_postgres_give_the_same_answers(tmp_path, monkeypatch, pg_store):
    on_sqlite = scenario(SQLiteStore(str(tmp_path / "parity.db")), monkeypatch)
    on_postgres = scenario(pg_store, monkeypatch)

    assert [s for s, _, _ in on_sqlite] == [s for s, _, _ in on_postgres]
    for (step, status_a, body_a), (_, status_b, body_b) in zip(on_sqlite, on_postgres):
        assert (status_a, body_a) == (status_b, body_b), f"different answer at step: {step}"

    # The scenario really exercised the store (guards against a silently empty run).
    statuses = {step: status for step, status, _ in on_postgres}
    assert statuses["register boss"] == 200 and statuses["name taken"] == 409
    assert statuses["login wrong pin"] == 401 and statuses["farmer cannot post"] == 403
    bodies = {step: body for step, _, body in on_postgres}
    assert [f["id"] for f in bodies["my fields"]["fields"]] == [1, 2]
    assert bodies["message for ' kök-say'"]["message"]["text"] == "Water turns start 20 April"
    assert bodies["message for 'Elsewhere'"]["message"] is None
    assert bodies["farmer inline, canal village"]["message"]["manager"] == "Mirab"
    assert bodies["farmer inline, no manager"]["message"] is None
