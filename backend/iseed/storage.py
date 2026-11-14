"""Where users, sessions, fields, canals and season messages live.

The API talks only to the Store methods below. SQLiteStore is for local work; the database
lane adds PostgresStore with the same methods (Vercel functions keep no files).
NASA results are never stored here: they stay in the committed files under data/.
"""
import hashlib
import json
import os
import secrets
import sqlite3
from datetime import date
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, role TEXT NOT NULL,
  region TEXT NOT NULL, village TEXT NOT NULL, pin TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS fields (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS canals (user_id INTEGER PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS messages (user_id INTEGER PRIMARY KEY, text TEXT NOT NULL, date TEXT NOT NULL);
"""


def hash_pin(pin, salt=None):
    salt = salt or secrets.token_hex(8)
    return salt + ":" + hashlib.pbkdf2_hmac("sha256", pin.encode(), salt.encode(), 100_000).hex()


def pin_matches(pin, stored):
    return secrets.compare_digest(hash_pin(pin, stored.split(":")[0]), stored)


def same_place(a, b):
    return a.strip().casefold() == b.strip().casefold()


class SQLiteStore:
    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def _user(self, row):
        return row and {k: row[k] for k in ("id", "name", "role", "region", "village")}

    # users and sessions
    def create_user(self, name, role, region, village, pin):
        """The new user, or None if the name is taken."""
        try:
            with self.db:
                cur = self.db.execute("INSERT INTO users (name, role, region, village, pin) VALUES (?,?,?,?,?)",
                                      (name.strip(), role, region.strip(), village.strip(), hash_pin(pin)))
        except sqlite3.IntegrityError:
            return None
        return self._user(self.db.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone())

    def check_pin(self, name, pin):
        row = self.db.execute("SELECT * FROM users WHERE name=?", (name.strip(),)).fetchone()
        return self._user(row) if row and pin_matches(pin, row["pin"]) else None

    def create_session(self, user_id):
        token = secrets.token_urlsafe(24)
        with self.db:
            self.db.execute("INSERT INTO sessions VALUES (?,?)", (token, user_id))
        return token

    def user_for_token(self, token):
        return self._user(self.db.execute(
            "SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=?", (token,)).fetchone())

    # fields
    def save_field(self, user_id, data):
        with self.db:
            return self.db.execute("INSERT INTO fields (user_id, data) VALUES (?,?)", (user_id, json.dumps(data))).lastrowid

    def fields_of(self, user_id):
        rows = self.db.execute("SELECT * FROM fields WHERE user_id=? ORDER BY id", (user_id,)).fetchall()
        return [{"id": r["id"], **json.loads(r["data"])} for r in rows]

    def field(self, field_id):
        r = self.db.execute("SELECT * FROM fields WHERE id=?", (field_id,)).fetchone()
        return r and {"id": r["id"], "userId": r["user_id"], **json.loads(r["data"])}

    # the manager's canal and season message
    def save_canal(self, user_id, data):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO canals VALUES (?,?)", (user_id, json.dumps(data)))

    def canal_of(self, user_id):
        r = self.db.execute("SELECT data FROM canals WHERE user_id=?", (user_id,)).fetchone()
        return r and json.loads(r["data"])

    def set_message(self, user_id, text):
        today = date.today().isoformat()
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO messages VALUES (?,?,?)", (user_id, text, today))
        return {"text": text, "date": today}

    def message_for(self, village):
        """The newest message of a manager whose own village or canal villages include this one."""
        rows = self.db.execute("SELECT m.*, u.name, u.village, c.data FROM messages m JOIN users u ON u.id=m.user_id "
                               "LEFT JOIN canals c ON c.user_id=m.user_id ORDER BY m.date DESC, m.user_id DESC").fetchall()
        for r in rows:
            villages = [r["village"]] + [v["name"] for v in (json.loads(r["data"])["villages"] if r["data"] else [])]
            if any(same_place(v, village) for v in villages):
                return {"text": r["text"], "date": r["date"], "manager": r["name"]}
        return None


def open_store():
    """SQLite file. On Vercel only /tmp is writable and it is wiped between cold starts,
    so accounts do not last there until the database lane adds PostgresStore."""
    default = "/tmp/iseed.db" if os.environ.get("VERCEL") else str(Path(__file__).resolve().parents[1] / "iseed.db")
    return SQLiteStore(os.environ.get("ISEED_DB", default))
