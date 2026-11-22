"""Build the semantic index from public EUvsDisinfo case descriptions."""

import gzip
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings
from app.ingest.narratives import load
from app.ingest.narrative_search import DIMENSIONS, INDEX_PATH, MODEL, case_digest, case_text, embeddings


def main():
    settings = Settings()
    if not settings.key:
        raise SystemExit("Missing API credential")
    cases = list({case["case_id"]: case for case in reversed(load())}.values())
    entries = []
    for offset in range(0, len(cases), 96):
        batch = cases[offset:offset + 96]
        vectors = embeddings(settings, [case_text(case) for case in batch], timeout=30)
        entries.extend((case["case_id"], case_digest(case), [round(value, 5) for value in vector])
                       for case, vector in zip(batch, vectors))
        print(f"Indexed {len(entries)} / {len(cases)}", flush=True)
    temporary = INDEX_PATH.with_suffix(".tmp")
    with gzip.open(temporary, "wt", encoding="utf-8") as stream:
        json.dump({"model": MODEL, "dimensions": DIMENSIONS, "entries": entries}, stream, separators=(",", ":"))
    temporary.replace(INDEX_PATH)


if __name__ == "__main__":
    main()
