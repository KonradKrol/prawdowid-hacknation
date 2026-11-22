"""Składa statyczną wersję prezentacji (docs/pitch/index.html) z plików slajdów.

    python scripts/build_pitch.py <katalog project/ z deck.json, deck.css i slides/>
"""
import json
from pathlib import Path
import re
import sys

BLOBS = {"f4c26b1b50fcb55f851f195f07dffdc7": "img/s_home.png", "9c595cf84fefe26254437f77b90d1327": "img/s_wynik.png",
         "ec1dda095732229ca86ffff890630ddf": "img/s_narracja2.png", "bf1ac7e93807b1c3e21d9f8b9c1d8277": "img/s_propozycja.png"}
source = Path(sys.argv[1])
target = Path(__file__).resolve().parents[1] / "docs" / "pitch"
deck = json.loads((source / "deck.json").read_text(encoding="utf-8"))
css = (source / "deck.css").read_text(encoding="utf-8")
slides = []
for slide_id in deck["order"]:
    html = (source / "slides" / f"{slide_id}.html").read_text(encoding="utf-8")
    for blob, path in BLOBS.items():
        html = html.replace(f"/_blob/{blob}", path)
    slides.append(re.sub(r"<aside>.*?</aside>", "", html, flags=re.S))
    (target / "slides").mkdir(parents=True, exist_ok=True)
    (target / "slides" / f"{slide_id}.html").write_text(html, encoding="utf-8")
(target / "deck.json").write_text(json.dumps(deck, ensure_ascii=False, indent=1), encoding="utf-8")
(target / "deck.css").write_text(css, encoding="utf-8")
page = f"""<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Prawdoskop — pitch</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700;800&family=Source+Serif+4:wght@400;600&display=swap">
<style>
* {{ margin:0; padding:0; }} html {{ background:#0C2142; }}
.stage {{ display:flex; flex-direction:column; align-items:center; gap:24px; padding:24px 0; }}
section {{ position:relative; width:1920px; height:1080px; overflow:hidden; flex:none; }}
table {{ border-collapse:collapse; }} th {{ text-align:left; font-weight:700; border-bottom:2px solid #14305C; padding:.35em .6em; }}
td {{ border-bottom:1px solid #C6CFDB; padding:.35em .6em; }}
{css}
</style></head><body><div class="stage">
{"".join(slides)}
</div></body></html>"""
(target / "index.html").write_text(page, encoding="utf-8")
print(len(slides), "slajdow:", target / "index.html")
