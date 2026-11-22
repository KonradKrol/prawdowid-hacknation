"""Odtwarzalne demo przebiegu moderatorskiego z jednym kanałem urzędowym (IMGW).

    python scripts/demo_moderacja.py                      # ewaluator demonstracyjny, osobna baza
    python scripts/demo_moderacja.py --live               # prawdziwy model (wymaga klucza w .env)
    python scripts/demo_moderacja.py --data-dir data/demo # zostawia bazę do obejrzenia w /moderacja

Kroki: cztery zgłoszenia (dwa o tym samym zdarzeniu innymi słowami, jedno o innym powiecie,
jedno o innym dniu) → import komunikatu bez związku → import ostrzeżenia o oblodzeniu →
powtórny import → korekta wpisu. Na końcu wypisuje stan spraw i propozycji.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FIXTURES = ROOT / "tests" / "fixtures"
REPORTS = (
    ("web", "Uwaga, 3 grudnia 2026 w powiecie bytowskim będzie gołoledź na drogach!"),
    ("adapter", "Słyszałem, że w pow. bytowskim 3.12.2026 drogi pokryje oblodzenie. Prawda?"),
    ("web", "3 grudnia 2026 oblodzenie w powiecie chojnickim, jedźcie ostrożnie"),
    ("web", "4 grudnia 2026 gołoledź w powiecie bytowskim"),
)
STEPS = (
    ("Komunikat bez związku ze sprawami (silny wiatr, Słupsk)", "imgw_demo_1_bez_sprawy.json"),
    ("Nowe ostrzeżenie: oblodzenie, powiaty bytowski i słupski, 3 grudnia", "imgw_demo_2_nowy.json"),
    ("Powtórny import tych samych wpisów", "imgw_demo_2_nowy.json"),
    ("Korekta: IMGW przedłuża ostrzeżenie do 14:00", "imgw_demo_3_korekta.json"),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="użyj modelu z .env zamiast ewaluatora demonstracyjnego")
    parser.add_argument("--data-dir", type=Path, help="katalog bazy (domyślnie tymczasowy, usuwany)")
    parser.add_argument("--json", type=Path, help="zapisz przebieg do pliku JSON")
    args = parser.parse_args()
    data_dir = args.data_dir or Path(tempfile.mkdtemp(prefix="prawdoskop-demo-"))
    if args.data_dir and data_dir.exists():
        shutil.rmtree(data_dir)
    os.environ.update(PRAWDOWID_DATA_DIR=str(data_dir), PRAWDOWID_ENV="development",
                      PRAWDOWID_EVALUATOR="live" if args.live else "fake", PRAWDOWID_PAID_CHECK_LIMIT="0")
    os.environ.setdefault("PRAWDOWID_CORPUS", str(ROOT / "Research" / "Prawdowid_Korpus_Probny.jsonl"))
    from app.core.service import get_service
    sys.stdout.reconfigure(encoding="utf-8")
    service = get_service()
    log = {"evaluator": service.settings.evaluator, "reports": [], "syncs": []}
    print(f"Ewaluator: {service.settings.evaluator}, baza: {data_dir}\n")
    print("1. Zgłoszenia")
    for channel, text in REPORTS:
        result = service.run(text, channel=channel, use_cache=False)
        label = result.items[0].label if result.items else result.status
        print(f"   [{channel:7}] {label:22} {text}")
        log["reports"].append({"channel": channel, "text": text, "label": label, "elapsed_ms": result.meta.elapsed_ms})
    print("\n   Sprawy:")
    for case in service.store.cases():
        print(f"   #{case['id']} {case['title']} · zgłoszeń: {case['reports']}")
        print(f"      brakujący dowód: {case['missing']}")
    print("\n2. Import IMGW")
    for title, name in STEPS:
        summary = service.official.sync(raw=json.loads((FIXTURES / name).read_text(encoding="utf-8")))
        print(f"   {title}: nowe {summary['new']}, zmienione {summary['changed']}, bez zmian {summary['unchanged']}, "
              f"propozycje {summary['proposals']}")
        log["syncs"].append({"step": title, **summary})
    print("\n3. Widok moderatora")
    for case in service.store.cases():
        proposals = service.store.proposals(case_id=case["id"])
        print(f"   #{case['id']} {case['title']} · zgłoszeń: {case['reports']} · propozycji: {len(proposals)}")
        for proposal in proposals:
            print(f"      wpis {proposal['entry_id']} v{proposal['version']}: "
                  f"{proposal['previous']['label']} → {proposal['proposed']['label']}")
            print(f"      cytat: „{proposal['quote']}”")
    status = service.official.status()
    print(f"\n   Wpisy w kanale: {status['entries']}, wersje: {status['versions']}, "
          f"dokumenty w korpusie: {len(service.corpus.sources)}")
    log["cases"] = [{**case, "proposals": service.store.proposals(case_id=case["id"])} for case in service.store.cases()]
    if args.json:
        args.json.write_text(json.dumps(log, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    service.corpus.close()
    if not args.data_dir:
        shutil.rmtree(data_dir, ignore_errors=True)
    else:
        print(f"\nPodgląd: PRAWDOWID_DATA_DIR={data_dir} uvicorn app.main:app → /moderacja")


if __name__ == "__main__":
    main()
