"""Pobiera przypadki EUvsDisinfo przez MCP i zostawia te, które dotyczą Polski.

Użycie: python scripts/euvs_fetch.py [--out Research/EUvsDisinfo_Surowe_PL.jsonl]
Token: PRAWDOWID_EUVS_TOKEN albo EUVSDISINFO_TOKEN w .env.
"""

import argparse
import html
import json
from pathlib import Path
import re
import sys
import time

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from app.ingest.narratives import fetch_cases  # noqa: E402

POLAND = re.compile(r"\b(Poland|Polish|Poles|Warsaw)\b", re.I)


def plain(value):
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def titles(rows):
    return [row.get("title") for row in rows or [] if isinstance(row, dict) and row.get("title")]


def about_poland(case):
    return "Poland" in titles(case.get("countries")) or bool(POLAND.search(case.get("title") or ""))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "Research" / "EUvsDisinfo_Surowe_PL.jsonl"))
    parser.add_argument("--page", type=int, default=100)
    args = parser.parse_args()
    kept, offset, total, started = [], 0, None, time.time()
    while total is None or offset < total:
        for attempt in range(3):
            try:
                cases = fetch_cases(offset=offset, limit=args.page)
                break
            except Exception as error:  # noqa: BLE001 - ponawiamy przy chwilowym błędzie serwera
                if attempt == 2:
                    raise
                print(f"offset {offset}: {error}; ponawiam", flush=True)
                time.sleep(3)
        if total is None:
            total = 19873
        if not cases:
            break
        for case in cases:
            if about_poland(case):
                kept.append({
                    "case_id": case["id"], "url": case["url"], "title": plain(case.get("title")),
                    "claim": plain(case.get("claim")), "fact": plain(case.get("fact"))[:1500],
                    "date": time.strftime("%Y-%m-%d", time.gmtime(case.get("date") or 0)),
                    "keywords": titles(case.get("keywords")), "countries": titles(case.get("countries")),
                })
        offset += len(cases)
        if offset % 2000 < args.page:
            print(f"{offset} przejrzanych, {len(kept)} o Polsce, {time.time() - started:.0f} s", flush=True)
    Path(args.out).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in kept), encoding="utf-8")
    print(f"gotowe: {offset} przejrzanych, {len(kept)} o Polsce -> {args.out}")


if __name__ == "__main__":
    main()
