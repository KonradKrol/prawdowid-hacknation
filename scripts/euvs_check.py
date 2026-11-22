"""Kontrola fałszywych trafień znanych narracji na zwykłych wiadomościach i pytaniach testowych.

Użycie: python scripts/euvs_check.py
Wypisuje wiadomości, które dostałyby etykietę „Znana narracja dezinformacyjna”, i nazwy narracji.
"""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ingest import narratives  # noqa: E402

cases = narratives.load()
texts = [line for line in (ROOT / "eval" / "narracje_neutralne.txt").read_text(encoding="utf-8").splitlines() if line.strip()]
for name in ("pytania_rozszerzenie.jsonl",):
    path = ROOT / "eval" / name
    if path.exists():
        texts += [json.loads(line)["input"] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
start = ROOT / "Research" / "Prawdowid_Proby_Start.jsonl"
if start.exists():
    for line in start.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            texts.append(row.get("input") or row.get("text") or row.get("question") or "")
hits = [(text, narratives.find(text, cases)[0]["narrative"]) for text in texts if text and narratives.find(text, cases)]
print(f"narracji: {len(cases)}")
print(f"ZWYKŁE wiadomości i pytania testowe: {len(texts)}, z etykietą (fałszywe trafienia): {len(hits)}")
for text, narrative in hits:
    print(f"  - {text[:90]!r} -> {narrative}")
repeats = [line for line in (ROOT / "eval" / "narracje_powtorzenia.txt").read_text(encoding="utf-8").splitlines() if line.strip()]
found = [(text, narratives.find(text, cases)) for text in repeats]
print(f"POWTÓRZENIA znanych narracji (napisane ręcznie): {len(repeats)}, rozpoznane: {sum(bool(f) for _, f in found)}")
for text, match in found:
    print(f"  {'+' if match else '-'} {text[:80]!r}" + (f" -> {match[0]['narrative']}" if match else ""))
