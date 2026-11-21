"""Merge curator-approved JSONL or CSV inputs into a new versioned corpus."""

import argparse
import csv
from datetime import date
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings
from app.core.model import Provider
from app.core.safety import SUSPICIOUS, sanitize
from prawdowid_core import REQUIRED_FIELDS


def records(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        if path.suffix.lower() == ".csv":
            yield from csv.DictReader(stream)
        else:
            yield from (json.loads(line) for line in stream if line.strip())


def normalize(row):
    if not isinstance(row, dict) or not all(isinstance(row.get(k), str) and row[k].strip() for k in REQUIRED_FIELDS):
        raise ValueError("Brak obowiązkowego pola tekstowego")
    result = {key: sanitize(value).strip() if isinstance(value, str) else value for key, value in row.items()}
    parsed = urlsplit(result["url"])
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None:
        raise ValueError("Niepoprawny URL źródła")
    if parsed.hostname != result["domain"] and not parsed.hostname.endswith("." + result["domain"]):
        raise ValueError("URL nie należy do podanej grupy domen")
    result["url"] = parsed._replace(fragment="").geturl().rstrip("/")
    result["published_on"] = result.get("published_on") or None
    for field in ("published_on", "checked_on"):
        if result.get(field):
            date.fromisoformat(result[field])
    if not result.get("usage"):
        raise ValueError("Brak informacji o warunkach użycia")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--llm-guard", action="store_true", help="Próba strażnika LLM dla nowych dokumentów; wymaga klucza.")
    args = parser.parse_args()
    provider = Provider(Settings()) if args.llm_guard else None
    if provider and not provider.settings.key:
        parser.error("Strażnik LLM wymaga klucza.")
    if args.output.exists():
        parser.error("Podaj nową ścieżkę wyjściową.")
    selected = {}
    urls = set()
    report = {"duplicates": 0, "quarantined": [], "invalid": []}
    for path in args.inputs:
        for position, row in enumerate(records(path), 1):
            try:
                source = normalize(row)
            except (ValueError, TypeError) as error:
                report["invalid"].append({"file": path.name, "record": position, "reason": str(error)})
                continue
            identifier = source["id"]
            if identifier in selected or source["url"] in urls:
                report["duplicates"] += 1
                continue
            flagged = bool(SUSPICIOUS.search(source["excerpt"]))
            if provider and not flagged:
                guard, _ = provider.guard(source["excerpt"][:3500])
                flagged = guard.contains_instructions and guard.confidence != "low"
            if flagged:
                report["quarantined"].append(identifier)
                continue
            selected[identifier] = source
            urls.add(source["url"])
    if selected:
        with args.output.open("x", encoding="utf-8") as stream:
            for source in selected.values():
                stream.write(json.dumps(source, ensure_ascii=False) + "\n")
    report.update(documents=len(selected), domains=len({r["domain"] for r in selected.values()}),
                  types=sorted({r["type"] for r in selected.values()}))
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if selected else 2


if __name__ == "__main__":
    raise SystemExit(main())
