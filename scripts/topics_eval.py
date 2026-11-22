"""Pomiar grupowania tematów na prawdziwym modelu.

Każda wiadomość z eval/tematy.jsonl przechodzi pełne sprawdzenie (bez pamięci podręcznej, osobna baza),
a potem porównujemy przydział do tematów z oczekiwanymi grupami:
- łączenie: odsetek par z tej samej grupy, które trafiły do jednego tematu,
- rozdzielanie: odsetek par z różnych grup, które trafiły do różnych tematów (fałszywe łączenia to błąd groźniejszy).
Użycie: python scripts/topics_eval.py [--same 0.67]
"""

import argparse
from itertools import combinations
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--same", type=float)
    parser.add_argument("--out", default=str(ROOT / "eval" / "tematy_wyniki.json"))
    args = parser.parse_args()
    os.environ["PRAWDOWID_DATA_DIR"] = tempfile.mkdtemp(prefix="tematy-")
    os.environ.setdefault("PRAWDOWID_CORPUS", str(ROOT / "Research" / "Prawdoskop_Korpus_v5.jsonl"))
    os.environ["PRAWDOWID_OFFICIAL_POLL_S"] = "0"
    from app.core import topics
    from app.core.service import Service
    from app.config import Settings
    if args.same is not None:
        topics.SAME = args.same
    rows = [json.loads(line) for line in (ROOT / "eval" / "tematy.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    service = Service(Settings())
    assigned, cost = [], 0.0
    for row in rows:
        result = service.run(row["text"], channel="api", use_cache=False)
        cost += result.meta.estimated_cost_usd or 0.0
        topic_id = None
        if result.status == "ok":
            with service.store.connection() as db:
                found = db.execute("SELECT topic_id FROM topic_reports WHERE check_id=?", (result.id,)).fetchone()
            topic_id = found[0] if found else None
        assigned.append({**row, "status": result.status, "topic": result.topic, "subject": result.subject, "topic_id": topic_id})
        print(f"{row['group']:<20} {result.status:<20} {topic_id!s:<4} {result.subject} | {result.topic}", flush=True)
    scored = [row for row in assigned if row["topic_id"] is not None]
    same = [(a, b) for a, b in combinations(scored, 2) if a["group"] == b["group"]]
    diff = [(a, b) for a, b in combinations(scored, 2) if a["group"] != b["group"]]
    joined = sum(a["topic_id"] == b["topic_id"] for a, b in same)
    separated = sum(a["topic_id"] != b["topic_id"] for a, b in diff)
    report = {
        "messages": len(rows), "grouped": len(scored), "skipped": [r["status"] for r in assigned if r["topic_id"] is None],
        "same_pairs": len(same), "joined": joined, "different_pairs": len(diff), "separated": separated,
        "false_merges": [(a["text"], b["text"]) for a, b in diff if a["topic_id"] == b["topic_id"]],
        "thresholds": {"same": topics.SAME, "window_h": topics.WINDOW_S // 3600},
        "cost_usd": round(cost, 4), "rows": assigned,
    }
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nłączenie: {joined}/{len(same)} par z tej samej grupy")
    print(f"rozdzielanie: {separated}/{len(diff)} par z różnych grup; fałszywe połączenia: {len(report['false_merges'])}")
    for a, b in report["false_merges"]:
        print(f"  ! {a!r} + {b!r}")
    print(f"pominięte (nie ok): {report['skipped']}, koszt: {report['cost_usd']} USD")


if __name__ == "__main__":
    main()
