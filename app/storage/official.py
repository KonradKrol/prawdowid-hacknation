"""Tabele SQLite dla kanału urzędowego, spraw zgłoszeń i propozycji dla moderatora."""

import json

OFFICIAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS official_entries (
  feed TEXT NOT NULL, entry_id TEXT NOT NULL, version INTEGER NOT NULL,
  content_hash TEXT NOT NULL, source TEXT NOT NULL, published_at TEXT NOT NULL,
  first_fetched_at TEXT NOT NULL, indexed_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
  PRIMARY KEY (feed, entry_id, version)
);
CREATE TABLE IF NOT EXISTS sync_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, feed TEXT NOT NULL, started_at TEXT NOT NULL,
  finished_at TEXT, status TEXT NOT NULL, fetched INTEGER DEFAULT 0, new INTEGER DEFAULT 0,
  changed INTEGER DEFAULT 0, unchanged INTEGER DEFAULT 0, rejected INTEGER DEFAULT 0,
  proposals INTEGER DEFAULT 0, error TEXT, duration_ms INTEGER
);
CREATE TABLE IF NOT EXISTS cases (
  id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT NOT NULL UNIQUE, hazard TEXT NOT NULL,
  counties TEXT NOT NULL, day TEXT NOT NULL, title TEXT NOT NULL, missing TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  reports INTEGER NOT NULL DEFAULT 0, text TEXT NOT NULL, last_result TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS case_reports (
  case_id INTEGER NOT NULL, created_at TEXT NOT NULL, text TEXT NOT NULL,
  check_id TEXT, channel TEXT
);
CREATE INDEX IF NOT EXISTS by_case ON case_reports(case_id);
CREATE TABLE IF NOT EXISTS proposals (
  id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER NOT NULL, source_id TEXT NOT NULL,
  feed TEXT NOT NULL, entry_id TEXT NOT NULL, version INTEGER NOT NULL, created_at TEXT NOT NULL,
  previous TEXT NOT NULL, proposed TEXT NOT NULL, quote TEXT, source_url TEXT,
  status TEXT NOT NULL DEFAULT 'pending', decided_at TEXT,
  UNIQUE (case_id, source_id)
);
"""


def _case(row):
    keys = ("id", "key", "hazard", "counties", "day", "title", "missing", "status", "created_at",
            "updated_at", "reports", "text", "last_result")
    case = dict(zip(keys, row))
    case["counties"] = json.loads(case["counties"])
    case["last_result"] = json.loads(case["last_result"])
    return case


def _proposal(row):
    keys = ("id", "case_id", "source_id", "feed", "entry_id", "version", "created_at", "previous",
            "proposed", "quote", "source_url", "status", "decided_at")
    proposal = dict(zip(keys, row))
    proposal["previous"] = json.loads(proposal["previous"])
    proposal["proposed"] = json.loads(proposal["proposed"])
    return proposal


class OfficialStore:
    """Metody dołączane do `Store`. Wymagają `self.connection()`."""

    # ---------- wpisy urzędowe ----------
    def official_latest(self, feed, entry_id):
        with self.connection() as db:
            row = db.execute(
                """SELECT version, content_hash, source FROM official_entries
                   WHERE feed=? AND entry_id=? ORDER BY version DESC LIMIT 1""", (feed, entry_id)).fetchone()
        return {"version": row[0], "content_hash": row[1], "source": json.loads(row[2])} if row else None

    def official_insert(self, feed, entry_id, version, content_hash, source, published_at, fetched_at, indexed_at):
        with self.connection() as db:
            return db.execute(
                "INSERT OR IGNORE INTO official_entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (feed, entry_id, version, content_hash, json.dumps(source, ensure_ascii=False),
                 published_at, fetched_at, indexed_at, fetched_at)).rowcount == 1

    def official_seen(self, feed, entry_id, version, seen_at):
        with self.connection() as db:
            db.execute("UPDATE official_entries SET last_seen_at=? WHERE feed=? AND entry_id=? AND version=?",
                       (seen_at, feed, entry_id, version))

    def official_current(self, feed=None):
        """Najnowsza wersja każdego wpisu."""
        with self.connection() as db:
            rows = db.execute(
                """SELECT e.source FROM official_entries e
                   JOIN (SELECT feed, entry_id, MAX(version) v FROM official_entries GROUP BY feed, entry_id) m
                     ON e.feed=m.feed AND e.entry_id=m.entry_id AND e.version=m.v
                   WHERE (? IS NULL OR e.feed=?) ORDER BY e.published_at""", (feed, feed)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def official_delete_simulated(self, feed, prefix):
        """Usuwa wszystkie wersje wpisów-symulacji. Zwraca identyfikatory rekordów korpusu."""
        with self.connection() as db:
            rows = db.execute("SELECT source FROM official_entries WHERE feed=? AND entry_id LIKE ?",
                              (feed, prefix + "%")).fetchall()
            db.execute("DELETE FROM official_entries WHERE feed=? AND entry_id LIKE ?", (feed, prefix + "%"))
            db.execute("DELETE FROM proposals WHERE feed=? AND entry_id LIKE ? AND status='pending'",
                       (feed, prefix + "%"))
        return [json.loads(row[0])["id"] for row in rows]

    def official_entries(self, feed):
        with self.connection() as db:
            rows = db.execute(
                """SELECT entry_id, version, published_at, first_fetched_at, indexed_at, last_seen_at
                   FROM official_entries WHERE feed=? ORDER BY first_fetched_at, entry_id, version""",
                (feed,)).fetchall()
        keys = ("entry_id", "version", "published_at", "first_fetched_at", "indexed_at", "last_seen_at")
        return [dict(zip(keys, row)) for row in rows]

    # ---------- przebiegi synchronizacji ----------
    def sync_start(self, feed, started_at):
        with self.connection() as db:
            return db.execute("INSERT INTO sync_runs (feed, started_at, status) VALUES (?, ?, 'running')",
                              (feed, started_at)).lastrowid

    def sync_finish(self, run_id, status, finished_at, duration_ms, error=None, **counts):
        fields = ("fetched", "new", "changed", "unchanged", "rejected", "proposals")
        with self.connection() as db:
            db.execute(
                f"""UPDATE sync_runs SET status=?, finished_at=?, duration_ms=?, error=?,
                    {", ".join(f"{name}=?" for name in fields)} WHERE id=?""",
                (status, finished_at, duration_ms, error, *(counts.get(name, 0) for name in fields), run_id))

    def sync_runs(self, feed, limit=10):
        with self.connection() as db:
            rows = db.execute(
                """SELECT id, started_at, finished_at, status, fetched, new, changed, unchanged, rejected,
                          proposals, error, duration_ms FROM sync_runs WHERE feed=? ORDER BY id DESC LIMIT ?""",
                (feed, limit)).fetchall()
        keys = ("id", "started_at", "finished_at", "status", "fetched", "new", "changed", "unchanged",
                "rejected", "proposals", "error", "duration_ms")
        return [dict(zip(keys, row)) for row in rows]

    # ---------- sprawy ----------
    def case_register(self, signature, title, missing, text, result_summary, check_id, channel, at):
        """Dodaje zgłoszenie do sprawy o tej samej sygnaturze albo zakłada nową sprawę."""
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT id FROM cases WHERE key=?", (signature.key,)).fetchone()
            if row is None:
                case_id = db.execute(
                    """INSERT INTO cases (key, hazard, counties, day, title, missing, status, created_at,
                                          updated_at, reports, text, last_result)
                       VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, 1, ?, ?)""",
                    (signature.key, signature.hazard, json.dumps(list(signature.counties)),
                     signature.day.isoformat(), title, missing, at, at, text,
                     json.dumps(result_summary, ensure_ascii=False))).lastrowid
            else:
                case_id = row[0]
                db.execute("UPDATE cases SET reports=reports+1, updated_at=? WHERE id=?", (at, case_id))
            db.execute("INSERT INTO case_reports VALUES (?, ?, ?, ?, ?)", (case_id, at, text, check_id, channel))
        return case_id

    def cases(self, status=None):
        with self.connection() as db:
            rows = db.execute("SELECT * FROM cases WHERE (? IS NULL OR status=?) ORDER BY updated_at DESC, id DESC",
                              (status, status)).fetchall()
        return [_case(row) for row in rows]

    def case(self, case_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        return _case(row) if row else None

    def case_reports(self, case_id):
        with self.connection() as db:
            rows = db.execute("SELECT created_at, text, check_id, channel FROM case_reports WHERE case_id=? "
                              "ORDER BY created_at", (case_id,)).fetchall()
        return [dict(zip(("created_at", "text", "check_id", "channel"), row)) for row in rows]

    # ---------- propozycje ----------
    def proposal_add(self, case_id, source, created_at, previous, proposed, quote):
        with self.connection() as db:
            cursor = db.execute(
                """INSERT OR IGNORE INTO proposals (case_id, source_id, feed, entry_id, version, created_at,
                                                    previous, proposed, quote, source_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (case_id, source["id"], source["feed"], source["entry_id"], source["version"], created_at,
                 json.dumps(previous, ensure_ascii=False), json.dumps(proposed, ensure_ascii=False), quote,
                 source["url"]))
            return cursor.lastrowid if cursor.rowcount == 1 else None

    def proposals(self, case_id=None, status=None):
        with self.connection() as db:
            rows = db.execute(
                """SELECT * FROM proposals WHERE (? IS NULL OR case_id=?) AND (? IS NULL OR status=?)
                   ORDER BY id""", (case_id, case_id, status, status)).fetchall()
        return [_proposal(row) for row in rows]

    def proposal_decide(self, proposal_id, accept, decided_at):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT case_id, proposed, status FROM proposals WHERE id=?", (proposal_id,)).fetchone()
            if row is None or row[2] != "pending":
                return False
            db.execute("UPDATE proposals SET status=?, decided_at=? WHERE id=?",
                       ("accepted" if accept else "rejected", decided_at, proposal_id))
            if accept:
                db.execute("UPDATE cases SET last_result=?, status='resolved', updated_at=? WHERE id=?",
                           (row[1], decided_at, row[0]))
            return True
