"""Rozpoznawanie zdarzenia lokalnego w zgłoszeniu: zjawisko, powiat (TERYT) i dzień.

Deterministyczne reguły, bez modelu językowego. Służą do łączenia zgłoszeń w sprawy
i do dopasowania ich do ostrzeżeń urzędowych. Ocena prawdziwości pozostaje w module
weryfikacji.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")
_FOLD = str.maketrans("ąćęłńóśźż", "acelnoszz")
WORD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
MONTHS = ("stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia",
          "wrzesnia", "pazdziernika", "listopada", "grudnia")
MONTHS_PL = ("stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia",
             "września", "października", "listopada", "grudnia")

# Kolejność ma znaczenie: pierwsze trafienie jest głównym zjawiskiem sprawy.
HAZARDS = (
    ("opady_marznace", "opady marznące", r"opad\w* marzn|marznac\w* (deszcz|mzawk)"),
    ("oblodzenie", "oblodzenie", r"oblodz|gololed|golole|slisk"),
    ("burze", "burze", r"burz|grad"),
    ("silny_wiatr", "silny wiatr", r"wiatr|wichur|porywy|orkan"),
    ("opady_sniegu", "opady śniegu", r"snieg|sniez|zawiej|zamiec"),
    ("silny_mroz", "silny mróz", r"mroz"),
    ("opady_deszczu", "opady deszczu", r"deszcz|ulew"),
    ("upal", "upał", r"upal"),
    ("mgla", "gęsta mgła", r"mgl"),
    ("roztopy", "roztopy", r"roztop"),
)
HAZARD_LABEL = {key: label for key, label, _ in HAZARDS}
ADJ_SUFFIXES = {"i", "iego", "im", "iemu", "ich", "iej", "ie", "a", "y", "ego", "emu", "ym"}
CITY_SUFFIXES = {"", "u", "a", "ie", "em", "owi", "y", "i", "iu"}
COUNTY = re.compile(r"^(powiat\w*|powiec\w*|pow)$")


def fold(text):
    return (text or "").casefold().translate(_FOLD)


@lru_cache(maxsize=1)
def gazetteer():
    data = json.loads((Path(__file__).with_name("powiaty.json")).read_text(encoding="utf-8"))["powiaty"]
    adjectives, cities, voivodeships = [], [], {}
    for code, row in data.items():
        name = row["name"]
        voivodeships.setdefault(fold(row["voivodeship"])[:-2], set()).add(code)
        if name.startswith("m. "):
            city = fold(name.removeprefix("m. st. ").removeprefix("m. "))
            if " " in city:
                continue  # Wielowyrazowe nazwy miast pomijamy w prototypie.
            stem = city[:-1] if city[-1] in "aeoyi" else city
            cities.append((stem, code))
        else:
            adjectives.append((fold(name)[:-1], code))
    return data, adjectives, cities, voivodeships


def hazards(text):
    folded = fold(text)
    return [key for key, _, pattern in HAZARDS if re.search(pattern, folded)]


def counties(text):
    """Kody TERYT powiatów wymienionych w tekście („w powiecie bytowskim”, „w Słupsku”)."""
    _, adjectives, cities, voivodeships = gazetteer()
    tokens = WORD.findall(fold(text))
    found, adjective_tokens = {}, set()
    for index, token in enumerate(tokens):
        window = tokens[max(0, index - 4):index]
        if any(COUNTY.match(word) for word in window):
            for stem, code in adjectives:
                if token.startswith(stem) and token[len(stem):] in ADJ_SUFFIXES:
                    found.setdefault(stem, set()).add(code)
                    adjective_tokens.add(index)
    for index, token in enumerate(tokens):
        if index in adjective_tokens:
            continue
        for stem, code in cities:
            if token.startswith(stem) and token[len(stem):] in CITY_SUFFIXES and len(stem) >= 3:
                found.setdefault("m:" + stem, set()).add(code)
    mentioned = set()
    for stem, codes in voivodeships.items():
        if any(token.startswith(stem) for token in tokens):
            mentioned |= codes
    result = set()
    for codes in found.values():
        narrowed = codes & mentioned if len(codes) > 1 and codes & mentioned else codes
        result |= narrowed
    return sorted(result)


NATIONWIDE = re.compile(r"\b(polsk\w*|kraj\w*|caly kraj|calej polsce|wojewodztw\w*|woj)\b")


def needs_place(text):
    """Krótkie pytanie o lokalne zjawisko pogodowe bez miejsca („Czy jutro będzie gołoledź?”).
    Ostrzeżenia IMGW dotyczą powiatów, więc bez miejsca nie da się ich dopasować."""
    if len(text) > 300 or not hazards(text) or counties(text):
        return False
    folded = fold(text)
    tokens = WORD.findall(folded)
    voivodeships = gazetteer()[3]
    return not NATIONWIDE.search(folded) and not any(token.startswith(stem) for token in tokens for stem in voivodeships)


def event_day(text, received):
    """Dzień zdarzenia: data podana wprost, „dziś/jutro/wczoraj” albo dzień otrzymania."""
    today = received.astimezone(WARSAW).date()
    folded = fold(text)
    if re.search(r"\bpojutrze\b", folded):
        return today + timedelta(days=2)
    if re.search(r"\bjutr\w*", folded):
        return today + timedelta(days=1)
    if re.search(r"\bwczoraj\w*", folded):
        return today - timedelta(days=1)
    if match := re.search(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")(?:\s+(\d{4}))?", folded):
        day, month = int(match[1]), MONTHS.index(match[2]) + 1
        year = int(match[3]) if match[3] else today.year
        try:
            return date(year, month, day)
        except ValueError:
            return today
    if match := re.search(r"\b(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?\b", folded):
        try:
            return date(int(match[3]) if match[3] else today.year, int(match[2]), int(match[1]))
        except ValueError:
            return today
    return today


@dataclass(frozen=True)
class Signature:
    hazard: str
    counties: tuple
    day: date

    @property
    def key(self):
        return f"{self.hazard}|{','.join(self.counties)}|{self.day.isoformat()}"

    def title(self):
        data = gazetteer()[0]
        names = ", ".join(county_label(code, data) for code in self.counties)
        return f"{HAZARD_LABEL[self.hazard].capitalize()} — {names}, {human_day(self.day)}"

    def missing(self):
        data = gazetteer()[0]
        names = ", ".join(county_label(code, data) for code in self.counties)
        return (f"Brakuje urzędowego komunikatu o zjawisku „{HAZARD_LABEL[self.hazard]}” dla obszaru: "
                f"{names} w dniu {human_day(self.day)}. Rozstrzygnie to ostrzeżenie IMGW obejmujące "
                f"ten powiat i dzień albo komunikat starostwa lub wojewódzkiego centrum zarządzania kryzysowego.")


def county_label(code, data=None):
    data = data or gazetteer()[0]
    row = data.get(code)
    if not row:
        return code
    name = row["name"]
    return name.removeprefix("m. st. ").removeprefix("m. ") if name.startswith("m. ") else f"powiat {name}"


def human_day(day):
    return f"{day.day} {MONTHS_PL[day.month - 1]} {day.year}"


def signature(text, received=None):
    """Zwraca sygnaturę zdarzenia lokalnego albo None, gdy brakuje zjawiska lub miejsca."""
    received = received or datetime.now(WARSAW)
    found_hazards = hazards(text)
    found_counties = counties(text)
    if not found_hazards or not found_counties:
        return None
    return Signature(found_hazards[0], tuple(found_counties), event_day(text, received))
