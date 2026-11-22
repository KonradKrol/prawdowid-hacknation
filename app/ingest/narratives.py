"""Znane narracje z bazy EUvsDisinfo: rozpoznanie powrotu starej narracji w nowej wiadomości.

Zasada: dopasowanie do udokumentowanego przypadku jest KONTEKSTEM, nie dowodem. Werdykt
o bieżącej wiadomości wynika wyłącznie z dowodów dotyczących tej sprawy (korpus, komunikaty).
Moduł zwraca link do przypadku, elementy wspólne i różnice istotne dla zgłoszenia
(data, miejsce, podpis/nadawca).

Dane: `Research/EUvsDisinfo_Przypadki.jsonl` (przypadki przygotowane przez kuratora: tłumaczenie
narracji na polskie znaczniki). Pobieranie nowych przypadków: `fetch_cases()` przez serwer MCP
EUvsDisinfo (streamable HTTP, token `PRAWDOWID_EUVS_TOKEN`).
"""

import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen

from app.ingest.places import fold

MCP_URL = "https://euvsdisinfo-mcp-server.vercel.app/mcp"
DEFAULT_PATH = Path(__file__).resolve().parents[2] / "Research" / "EUvsDisinfo_Przypadki.jsonl"
SIGNATURE = re.compile(r"(podpisan\w*|podpis|w imieniu|komunikat|rozkaz|oświadczeni\w*)\s*:?\s*([A-ZŁŚŻŹĆŃÓ][\w .,-]{3,60})")
AUTHORITY = re.compile(r"(Sztab Generalny[\w ]*|Ministerstw\w+ Obrony Narodowej|MON|Dowództw\w+ Operacyjn\w+|"
                       r"Kancelari\w+ Prezydenta|Rządow\w+ Centrum Bezpieczeństwa|RCB|Wojsk\w+ Polsk\w+)")
DATE = re.compile(r"\b(\d{1,2})[. ](\d{1,2}|stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|"
                  r"września|października|listopada|grudnia)[. ](20\d\d)\b", re.I)
PLACES = ("Lwów", "Lwowa", "Lwowie", "Wołyń", "Wołyniu", "Łuck", "Łucku", "Równe", "Tarnopol", "Grodno", "Brześć",
          "Przemyśl", "Przemyśla", "Medyka", "Medyce", "Hrubieszów", "Chełm")


def load(path=None):
    path = Path(path or os.getenv("PRAWDOWID_NARRATIVES", DEFAULT_PATH))
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def matches(case, text):
    folded = fold(text)
    return all(any(fold(marker) in folded for marker in group) for group in case["markers"])


def compare(case, text):
    """Elementy wspólne i różnice między zgłoszeniem a udokumentowanym przypadkiem."""
    dates = [m.group(0) for m in DATE.finditer(text)]
    places = sorted({place for place in PLACES if place in text})
    authority = AUTHORITY.search(text)
    signed = SIGNATURE.search(text)
    differences = []
    if dates:
        differences.append(f"nowa data: {', '.join(dates)} (przypadek EUvsDisinfo z {case['date']})")
    if places:
        differences.append(f"konkretne miejsce: {', '.join(places)} (przypadek: {', '.join(case['places'])})")
    if authority or signed:
        who = (authority.group(0) if authority else signed.group(2)).strip()
        differences.append(f"podpis lub nadawca: {who} (przypadek: {case['attribution']})")
    return {
        "case_id": case["case_id"], "url": case["url"], "title": case["title"], "date": case["date"],
        "narrative": case["narrative"], "shared": [case["narrative"]] + [f"motyw: {tag}" for tag in case["tags"][-2:]],
        "differences": differences, "recurrences": len(case.get("recurrences", [])) + 1,
        "claim": case["claim"], "fact": case["fact"],
    }


def find(text, cases):
    return [compare(case, text) for case in cases if matches(case, text)]


def notice_text(match):
    """Jedno krótkie zdanie. Szczegóły (różnice, liczba powrotów) zostają w danych dla moderatora."""
    return f"„{match['narrative']}” — znana narracja dezinformacyjna opisana przez EUvsDisinfo."


# ---------- pobieranie przypadków z serwera MCP ----------

def _post(payload, token, session=None, timeout=30):
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
               "Authorization": f"Bearer {token}"}
    if session:
        headers["mcp-session-id"] = session
    request = Request(MCP_URL, data=json.dumps(payload).encode(), headers=headers, method="POST")
    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        session = response.headers.get("mcp-session-id") or session
    data = [line[5:].strip() for line in body.splitlines() if line.startswith("data:")]
    return json.loads(data[-1] if data else body), session


def fetch_cases(token=None, offset=0, limit=100):
    """Zwraca listę przypadków (pola id, title, claim, fact, date, url, keywords, countries)."""
    token = token or os.getenv("PRAWDOWID_EUVS_TOKEN", "")
    if not token:
        raise PermissionError("Brak tokenu EUvsDisinfo (PRAWDOWID_EUVS_TOKEN)")
    _, session = _post({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
        "protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "prawdoskop", "version": "1.0"}}}, token)
    result, _ = _post({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "cases", "arguments": {"offset": offset, "limit": limit}}}, token, session)
    return result["result"]["structuredContent"]["cases"]
