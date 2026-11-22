"""Kanał urzędowy: ostrzeżenia meteorologiczne IMGW-PIB (danepubliczne.imgw.pl).

API zwraca bieżące ostrzeżenia jako listę JSON, bez klucza. Każdy wpis ma identyfikator,
czas publikacji, okres ważności i listę kodów TERYT powiatów. API nie podaje numeru
korekty, więc wersję wpisu wyznaczamy po skrócie treści: ten sam identyfikator z inną
treścią, ważnością lub obszarem to nowa wersja.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import json
from urllib.request import Request, urlopen

from app.ingest.places import WARSAW, county_label, gazetteer, hazards

FEED = "imgw-meteo"
URL = "https://danepubliczne.imgw.pl/api/data/warningsmeteo"
PUBLISHER = "Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut Badawczy"
USAGE = ("Źródłem pochodzenia danych jest Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut "
         "Badawczy. Dane Instytutu Meteorologii i Gospodarki Wodnej – Państwowego Instytutu Badawczego "
         "zostały przetworzone (wybór pól i skrót).")
USER_AGENT = "Prawdoskop/1.0 (prototyp HackNation; import ostrzezen)"


@dataclass(frozen=True)
class Entry:
    entry_id: str
    event: str
    level: str
    probability: str
    published_at: datetime
    valid_from: datetime
    valid_to: datetime
    text: str
    comment: str
    office: str
    teryt: tuple

    @property
    def content_hash(self):
        canonical = [self.event, self.level, self.probability, self.published_at.isoformat(),
                     self.valid_from.isoformat(), self.valid_to.isoformat(), self.text, self.comment,
                     self.office, list(self.teryt)]
        return sha256(json.dumps(canonical, ensure_ascii=False).encode()).hexdigest()

    @property
    def hazards(self):
        return hazards(self.event) or hazards(self.text)


def local_time(value):
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=WARSAW)


def fetch(url=URL, timeout=15):
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise OSError(f"IMGW HTTP {response.status}")
        return json.load(response)


def parse(raw):
    """Zwraca (wpisy, liczba_odrzuconych). Niekompletny wpis nie przerywa importu."""
    if not isinstance(raw, list):
        raise ValueError("IMGW: oczekiwano listy ostrzeżeń")
    entries, rejected = [], 0
    for row in raw:
        try:
            teryt = tuple(sorted({str(code) for code in row["teryt"] if str(code).isdigit() and len(str(code)) == 4}))
            entry = Entry(
                entry_id=str(row["id"]), event=row["nazwa_zdarzenia"].strip(), level=str(row["stopien"]),
                probability=str(row.get("prawdopodobienstwo") or ""),
                published_at=local_time(row["opublikowano"]), valid_from=local_time(row["obowiazuje_od"]),
                valid_to=local_time(row["obowiazuje_do"]), text=" ".join(row["tresc"].split()),
                comment=" ".join((row.get("komentarz") or "").split()), office=row.get("biuro") or "",
                teryt=teryt,
            )
            if not entry.entry_id or not entry.text or not teryt:
                raise ValueError("pusty wpis")
            entries.append(entry)
        except (KeyError, TypeError, ValueError, AttributeError):
            rejected += 1
    return entries, rejected


def area_line(entry):
    data = gazetteer()[0]
    names = ", ".join(county_label(code, data) for code in entry.teryt)
    return (f"Ostrzeżenie obowiązuje od {entry.valid_from:%d.%m.%Y %H:%M} do {entry.valid_to:%d.%m.%Y %H:%M} "
            f"i obejmuje obszar: {names}.")


def to_source(entry, version, fetched_at):
    """Rekord korpusu z jednym wpisem IMGW. Drugi fragment to dosłowny zapis pól ważności i obszaru."""
    data = gazetteer()[0]
    names = [county_label(code, data) for code in entry.teryt]
    short = ", ".join(names[:6]) + (f" i {len(names) - 6} innych" if len(names) > 6 else "")
    return {
        "id": f"imgw-{entry.entry_id}-v{version}",
        "title": f"Ostrzeżenie IMGW: {entry.event} ({entry.level}. stopnia) – {short}",
        "publisher": PUBLISHER,
        "type": "urzędowe",
        "kind": "ostrzeżenie",
        "domain": "imgw.pl",
        "host": "danepubliczne.imgw.pl",
        "url": f"{URL}#{entry.entry_id}",
        "language": "pl",
        "published_on": entry.published_at.date().isoformat(),
        "checked_on": fetched_at.astimezone(WARSAW).date().isoformat(),
        "archival": False,
        "places": names,
        "topics": [entry.event, "ostrzeżenie meteorologiczne"],
        "excerpts": [entry.text, area_line(entry)],
        "scope": (f"Ostrzeżenie meteorologiczne IMGW-PIB „{entry.event}”, stopień {entry.level}, "
                  f"prawdopodobieństwo {entry.probability}%, wydane {entry.published_at:%d.%m.%Y %H:%M} "
                  f"przez: {entry.office}. Drugi fragment zapisuje pola ważności i obszaru (TERYT) z API. "
                  f"Wersja wpisu {version}."),
        "usage": USAGE,
        "feed": FEED,
        "entry_id": entry.entry_id,
        "version": version,
        "teryt": list(entry.teryt),
        "hazards": entry.hazards,
        "valid_from": entry.valid_from.isoformat(),
        "valid_to": entry.valid_to.isoformat(),
        "published_at": entry.published_at.isoformat(),
    }


def covers(source, signature):
    """Czy wpis dotyczy sprawy: to samo zjawisko, wspólny powiat, dzień w okresie ważności."""
    if signature.hazard not in source.get("hazards", []):
        return False
    if not set(signature.counties) & set(source.get("teryt", [])):
        return False
    start = datetime.fromisoformat(source["valid_from"]).date()
    end = (datetime.fromisoformat(source["valid_to"]) - timedelta(minutes=1)).date()
    return start <= signature.day <= end
