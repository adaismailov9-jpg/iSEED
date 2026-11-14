"""Where users, sessions, fields, canals, season messages and wrong-PIN records live.

The API talks only to the Store methods below. SQLiteStore is for local work; the database
lane adds PostgresStore with the same methods (Vercel functions keep no files).
NASA results are never stored here: they stay in the committed files under data/.
"""
import hashlib
import json
import os
import secrets
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

SESSION_DAYS = 30          # a sign-in lasts 30 days, then the user signs in again
FAILURES_KEPT = timedelta(days=1)  # wrong-PIN records older than this are deleted

# Sessions keep only a SHA-256 hash of the token, so a copy of the database holds no usable token.
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, role TEXT NOT NULL,
  region TEXT NOT NULL, village TEXT NOT NULL, pin TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS fields (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS canals (user_id INTEGER PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS messages (user_id INTEGER PRIMARY KEY, text TEXT NOT NULL, date TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS login_failures (name TEXT NOT NULL, ip TEXT NOT NULL, at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ix_login_failures_name_at ON login_failures (name, at);
CREATE INDEX IF NOT EXISTS ix_login_failures_ip_at ON login_failures (ip, at);
"""


def utcnow():
    """The clock both stores use (tests move it forward)."""
    return datetime.now(timezone.utc)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


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
        # An older iseed.db kept plain-text tokens: drop that table (everyone simply signs in again).
        columns = [r["name"] for r in self.db.execute("PRAGMA table_info(sessions)")]
        if columns and "token_hash" not in columns:
            with self.db:
                self.db.execute("DROP TABLE sessions")
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
        """A new token. Only its hash is stored; expired sessions are cleaned up on the way."""
        token, now = secrets.token_urlsafe(24), utcnow()
        with self.db:
            self.db.execute("DELETE FROM sessions WHERE expires <= ?", (now.timestamp(),))
            self.db.execute("INSERT INTO sessions VALUES (?,?,?)",
                            (token_hash(token), user_id, (now + timedelta(days=SESSION_DAYS)).timestamp()))
        return token

    def user_for_token(self, token):
        """The user of a valid, unexpired session, else None."""
        return self._user(self.db.execute(
            "SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token_hash=? AND s.expires > ?",
            (token_hash(token), utcnow().timestamp())).fetchone())

    def delete_session(self, token):
        """Sign out: this token stops working; the user's other sessions stay."""
        with self.db:
            self.db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(token),))

    def delete_sessions_of(self, user_id, keep=None):
        """Sign out everywhere, except the session of the token `keep` if given."""
        with self.db:
            self.db.execute("DELETE FROM sessions WHERE user_id=? AND token_hash IS NOT ?",
                            (user_id, keep and token_hash(keep)))

    def update_user(self, user_id, name=None, region=None, village=None, pin=None):
        """Change the given values. The updated user, or None if the new name is taken."""
        changes = {k: v.strip() for k, v in (("name", name), ("region", region), ("village", village)) if v is not None}
        if pin is not None:
            changes["pin"] = hash_pin(pin)
        if changes:
            try:
                with self.db:
                    self.db.execute(f"UPDATE users SET {', '.join(k + '=?' for k in changes)} WHERE id=?",
                                    (*changes.values(), user_id))
            except sqlite3.IntegrityError:
                return None
        return self._user(self.db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())

    def delete_user(self, user_id):
        """The account and everything of it: sessions, fields, canal and season message."""
        with self.db:
            for table in ("sessions", "fields", "canals", "messages"):
                self.db.execute(f"DELETE FROM {table} WHERE user_id=?", (user_id,))
            self.db.execute("DELETE FROM users WHERE id=?", (user_id,))

    # wrong-PIN records, for the /login limit
    def failed_logins(self, name, ip, since):
        """(wrong PINs for this name, wrong PINs from this IP) after `since`."""
        s = since.timestamp()
        count = "SELECT count(*) FROM login_failures WHERE {} = ? AND at > ?"
        return (self.db.execute(count.format("name"), (name.strip(), s)).fetchone()[0],
                self.db.execute(count.format("ip"), (ip, s)).fetchone()[0])

    def add_failed_login(self, name, ip):
        now = utcnow()
        with self.db:
            self.db.execute("DELETE FROM login_failures WHERE at <= ?", ((now - FAILURES_KEPT).timestamp(),))
            self.db.execute("INSERT INTO login_failures VALUES (?,?,?)", (name.strip(), ip, now.timestamp()))

    def clear_failed_logins(self, name):
        with self.db:
            self.db.execute("DELETE FROM login_failures WHERE name=?", (name.strip(),))

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

    def update_field(self, user_id, field_id, data):
        """Replace a field's data. False if there is no such field of this user."""
        with self.db:
            return self.db.execute("UPDATE fields SET data=? WHERE id=? AND user_id=?",
                                   (json.dumps(data), field_id, user_id)).rowcount > 0

    def delete_field(self, user_id, field_id):
        """False if there is no such field of this user."""
        with self.db:
            return self.db.execute("DELETE FROM fields WHERE id=? AND user_id=?", (field_id, user_id)).rowcount > 0

    # the manager's canal and season message
    def save_canal(self, user_id, data):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO canals VALUES (?,?)", (user_id, json.dumps(data)))

    def canal_of(self, user_id):
        r = self.db.execute("SELECT data FROM canals WHERE user_id=?", (user_id,)).fetchone()
        return r and json.loads(r["data"])

    def delete_canal(self, user_id):
        """False if this manager had no canal."""
        with self.db:
            return self.db.execute("DELETE FROM canals WHERE user_id=?", (user_id,)).rowcount > 0

    def delete_message(self, user_id):
        """Take the season message down. False if there was none."""
        with self.db:
            return self.db.execute("DELETE FROM messages WHERE user_id=?", (user_id,)).rowcount > 0

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


def _load_env_file():
    """Read backend/.env if python-dotenv is installed. Real environment variables win (Vercel)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


def open_store():
    """PostgresStore when DATABASE_URL is set (Neon on Vercel, Docker locally); otherwise SQLite in backend/iseed.db."""
    _load_env_file()
    url = os.environ.get("DATABASE_URL")
    if url:
        from .pgstore import PostgresStore  # imported only here: SQLite users need no Postgres packages
        return PostgresStore(url)
    return SQLiteStore(os.environ.get("ISEED_DB", str(Path(__file__).resolve().parents[1] / "iseed.db")))
