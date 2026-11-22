"""Pomiar: ile czasu mija od publikacji ostrzeżenia IMGW do jego pojawienia się w Prawdoskopie.

    python scripts/measure_imgw_lag.py --interval 120 --duration 10800 --out eval/imgw_lag.json

Działa na osobnej bazie i ewaluatorze demonstracyjnym (bez kosztów modelu). Opóźnienie liczymy
tylko dla wpisów, które pojawiły się po pierwszym pobraniu; wpisy obecne w pierwszym pobraniu
to zaległość i raportujemy je osobno. Wynik zależy od interwału odpytywania: górna granica
opóźnienia ≈ czas publikacji w API + interwał + czas importu.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=120)
    parser.add_argument("--duration", type=int, default=3600)
    parser.add_argument("--out", type=Path, default=ROOT / "eval" / "imgw_lag.json")
    args = parser.parse_args()
    data_dir = Path(tempfile.mkdtemp(prefix="prawdoskop-lag-"))
    os.environ.update(PRAWDOWID_DATA_DIR=str(data_dir), PRAWDOWID_ENV="development", PRAWDOWID_EVALUATOR="fake")
    os.environ.setdefault("PRAWDOWID_CORPUS", str(ROOT / "Research" / "Prawdowid_Korpus_Probny.jsonl"))
    from app.core.service import get_service
    service = get_service()
    started = time.monotonic()
    runs = []
    while time.monotonic() - started < args.duration:
        summary = service.official.sync()
        runs.append({"at": datetime.now(timezone.utc).isoformat(), **{k: summary.get(k) for k in
                     ("status", "error", "fetched", "new", "changed", "unchanged", "rejected")}})
        status = service.official.status()
        entries = service.store.official_entries(service.official.feed)
        report = {
            "source": "https://danepubliczne.imgw.pl/api/data/warningsmeteo",
            "interval_s": args.interval, "started": runs[0]["at"], "last": runs[-1]["at"], "polls": len(runs),
            "failed_polls": sum(run["status"] == "error" for run in runs),
            "lag": status["lag"], "entries": entries, "runs": runs,
            "median_import_ms": sorted(r["duration_ms"] or 0 for r in service.store.sync_runs(service.official.feed, 1000))[len(runs) // 2],
        }
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
