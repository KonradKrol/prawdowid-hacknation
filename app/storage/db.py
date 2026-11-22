from contextlib import closing, contextmanager
from datetime import datetime, timezone
import json
import sqlite3

from app.contract import CheckResult
from app.storage.official import OFFICIAL_SCHEMA, OfficialStore

CHECK_TTL = 7 * 86400
EVENT_TTL = 30 * 86400


class Store(OfficialStore):
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS checks (
                  id TEXT PRIMARY KEY, session TEXT, created INTEGER NOT NULL,
                  payload TEXT NOT NULL, root_input TEXT NOT NULL, rounds INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS by_session ON checks(session);
                CREATE TABLE IF NOT EXISTS events (
                  created INTEGER NOT NULL, kind TEXT NOT NULL, check_id TEXT,
                  detail TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS result_cache (
                  key TEXT PRIMARY KEY, created INTEGER NOT NULL, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS whatsapp_messages (
                  id TEXT PRIMARY KEY, created INTEGER NOT NULL, payload TEXT
                );
                CREATE TABLE IF NOT EXISTS rate_hits (
                  bucket TEXT NOT NULL, created INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS by_bucket ON rate_hits(bucket, created);
                CREATE TABLE IF NOT EXISTS paid_check_budget (
                  id INTEGER PRIMARY KEY CHECK (id = 1), used INTEGER NOT NULL
                );
            """)
            db.executescript(OFFICIAL_SCHEMA)

    @contextmanager
    def connection(self):
        with closing(sqlite3.connect(self.path, timeout=5)) as db, db:
            yield db

    def prune(self, now):
        with self.connection() as db:
            for table, ttl in (("checks", CHECK_TTL), ("events", EVENT_TTL),
                               ("result_cache", CHECK_TTL), ("whatsapp_messages", CHECK_TTL),
                               ("rate_hits", 86400)):
                db.execute(f"DELETE FROM {table} WHERE created < ?", (now - ttl,))

    def save(self, result, session, root_input, rounds):
        if not session:
            return
        created = int(datetime.fromisoformat(result.created_at).timestamp())
        with self.connection() as db:
            db.execute("INSERT INTO checks VALUES (?, ?, ?, ?, ?, ?)",
                       (result.id, session, created, result.model_dump_json(), root_input, rounds))

    def read(self, check_id, session=None):
        now = int(datetime.now(timezone.utc).timestamp())
        with self.connection() as db:
            row = db.execute(
                """SELECT payload, root_input, rounds FROM checks
                   WHERE id=? AND created>=? AND (? IS NULL OR session=?)""",
                (check_id, now - CHECK_TTL, session, session),
            ).fetchone()
        return (CheckResult.model_validate_json(row[0]), row[1], row[2]) if row else None

    def delete(self, session, check_id=None):
        with self.connection() as db:
            if check_id is None:
                return db.execute("DELETE FROM checks WHERE session=?", (session,)).rowcount
            return db.execute("DELETE FROM checks WHERE session=? AND id=?", (session, check_id)).rowcount

    def event(self, now, kind, check_id, detail):
        with self.connection() as db:
            db.execute("INSERT INTO events VALUES (?, ?, ?, ?)", (now, kind, check_id, json.dumps(detail)))

    def charge(self, bucket, now):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            day, minute = db.execute(
                "SELECT COUNT(*), COALESCE(SUM(created>=?),0) FROM rate_hits WHERE bucket=? AND created>=?",
                (now - 60, bucket, now - 86400),
            ).fetchone()
            if minute >= 10 or day >= 100:
                return False
            db.execute("INSERT INTO rate_hits VALUES (?, ?)", (bucket, now))
            return True

    def reserve_paid_check(self, limit):
        with self.connection() as db:
            cursor = db.execute("""
                INSERT INTO paid_check_budget VALUES (1, 1)
                ON CONFLICT(id) DO UPDATE SET used = used + 1 WHERE used < ?
            """, (limit,))
            return cursor.rowcount == 1

    def cached(self, key, now):
        with self.connection() as db:
            row = db.execute("SELECT payload FROM result_cache WHERE key=? AND created>=?", (key, now - CHECK_TTL)).fetchone()
        return CheckResult.model_validate_json(row[0]) if row else None

    def cache(self, key, now, result):
        with self.connection() as db:
            db.execute("INSERT OR REPLACE INTO result_cache VALUES (?, ?, ?)", (key, now, result.model_dump_json()))

    def reserve_message(self, message_id, now):
        with self.connection() as db:
            return db.execute("INSERT OR IGNORE INTO whatsapp_messages VALUES (?, ?, NULL)", (message_id, now)).rowcount == 1

    def message(self, message_id):
        with self.connection() as db:
            row = db.execute("SELECT payload FROM whatsapp_messages WHERE id=?", (message_id,)).fetchone()
        return json.loads(row[0]) if row and row[0] else None

    def finish_message(self, message_id, response):
        with self.connection() as db:
            db.execute("UPDATE whatsapp_messages SET payload=? WHERE id=?", (json.dumps(response), message_id))

    def release_message(self, message_id):
        with self.connection() as db:
            db.execute("DELETE FROM whatsapp_messages WHERE id=? AND payload IS NULL", (message_id,))
