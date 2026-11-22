"""Tabele SQLite dla tematów zgłoszeń (grupowanie w panelu moderatora)."""

import json

TOPICS_SCHEMA = """
CREATE TABLE IF NOT EXISTS topics (
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, stems TEXT NOT NULL,
  sources TEXT NOT NULL, created INTEGER NOT NULL, updated INTEGER NOT NULL, reports INTEGER NOT NULL,
  subject TEXT
);
CREATE TABLE IF NOT EXISTS topic_reports (
  topic_id INTEGER NOT NULL, created INTEGER NOT NULL, check_id TEXT, channel TEXT,
  label TEXT, topic TEXT NOT NULL, text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS by_topic ON topic_reports(topic_id, created);
"""


class TopicStore:
    def topics_recent(self, since):
        with self.connection() as db:
            rows = db.execute("SELECT id, title, stems, sources FROM topics WHERE updated >= ?", (since,)).fetchall()
        return [{"id": r[0], "title": r[1], "stems": json.loads(r[2]), "sources": json.loads(r[3])} for r in rows]

    def topic_add(self, title, stems, sources, now, subject=None):
        with self.connection() as db:
            return db.execute("INSERT INTO topics (title, stems, sources, created, updated, reports, subject) VALUES (?, ?, ?, ?, ?, 0, ?)",
                              (title, json.dumps(stems), json.dumps(sorted(sources)), now, now, subject)).lastrowid

    def topic_subjects(self, since, limit=40):
        with self.connection() as db:
            rows = db.execute("SELECT DISTINCT subject FROM topics WHERE updated >= ? AND subject IS NOT NULL "
                              "ORDER BY updated DESC LIMIT ?", (since, limit)).fetchall()
        return [row[0] for row in rows]

    def topic_report(self, topic_id, now, check_id, channel, label, topic, text, sources):
        with self.connection() as db:
            row = db.execute("SELECT sources FROM topics WHERE id=?", (topic_id,)).fetchone()
            merged = sorted(set(json.loads(row[0])) | set(sources))[:20]
            db.execute("UPDATE topics SET updated=?, reports=reports+1, sources=? WHERE id=?",
                       (now, json.dumps(merged), topic_id))
            db.execute("INSERT INTO topic_reports VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (topic_id, now, check_id, channel, label, topic, text[:600]))

    def topics_board(self, now, since, limit=30, *, hourly_threshold, daily_threshold):
        """Tematy z ostatnich dni: liczba zgłoszeń w ostatniej godzinie i dobie, rozkład ocen i ostatnie treści."""
        with self.connection() as db:
            rows = db.execute(
                """SELECT t.id, t.title, t.reports, t.created, t.updated,
                          (SELECT COUNT(*) FROM topic_reports r WHERE r.topic_id=t.id AND r.created >= ?) AS last_hour,
                          (SELECT COUNT(*) FROM topic_reports r WHERE r.topic_id=t.id AND r.created >= ?) AS last_day
                   FROM topics t WHERE t.updated >= ?
                   ORDER BY CASE WHEN last_hour >= ? THEN 2 WHEN last_day >= ? THEN 1 ELSE 0 END DESC,
                            last_hour DESC, last_day DESC, t.updated DESC LIMIT ?""",
                (now - 3600, now - 86400, since, hourly_threshold, daily_threshold, limit)).fetchall()
            board = []
            for topic_id, title, reports, created, updated, last_hour, last_day in rows:
                labels = dict(db.execute("SELECT COALESCE(label, 'brak'), COUNT(*) FROM topic_reports WHERE topic_id=? GROUP BY 1",
                                         (topic_id,)).fetchall())
                recent = []
                for created_at, channel, text, topic, context in db.execute(
                    """SELECT r.created, r.channel, r.text, r.topic, c.root_input
                       FROM topic_reports r LEFT JOIN checks c ON c.id=r.check_id AND c.rounds > 0
                       WHERE r.topic_id=? ORDER BY r.created DESC LIMIT 10""",
                    (topic_id,),
                ):
                    if context:
                        text = " · ".join(line.strip() for line in context.splitlines() if line.strip())
                        if len(text) > 600:
                            text = text[:400] + " … " + text[-195:]
                    recent.append({"created": created_at, "channel": channel, "text": text, "topic": topic})
                board.append({"id": topic_id, "title": title, "reports": reports, "created": created, "updated": updated,
                              "last_hour": last_hour, "last_day": last_day, "labels": labels, "recent": recent})
        return board

    def topics_prune(self, before):
        with self.connection() as db:
            db.execute("DELETE FROM topic_reports WHERE created < ?", (before,))
            db.execute("DELETE FROM topics WHERE id NOT IN (SELECT DISTINCT topic_id FROM topic_reports)")
