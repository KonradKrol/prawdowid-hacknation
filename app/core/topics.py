"""Grupowanie zgłoszeń w tematy dla panelu moderatora.

Podejście mieszane i prawie darmowe:
1. Model (guard, i tak wywoływany przy każdym sprawdzeniu) zwraca dwa krótkie pola:
   - topic: tytuł do panelu, np. „dymisja ministra spraw zagranicznych”,
   - subject: sam przedmiot sprawy w urzędowej formie, np. „minister spraw zagranicznych”.
   Szef MSZ, szef dyplomacji i minister spraw zagranicznych dają ten sam przedmiot.
2. Kod łączy zgłoszenia po przedmiocie: rdzenie słów (pierwsze 6 liter, bez polskich znaków),
   część wspólna / mniejszy zbiór >= SAME, w oknie 48 godzin.
   „Dymisja”, „rezygnacja” i „odejście” nie przeszkadzają, bo nie należą do przedmiotu,
   a „minister zdrowia” i „minister spraw zagranicznych” mają tylko 1 z 2 rdzeni wspólny (0,5 < 0,67).
Brak pól od modelu (np. awaria): bierzemy tezę z wyniku.
Pomiar: scripts/topics_eval.py na eval/tematy.jsonl.
"""

import re

from app.ingest.places import fold

WINDOW_S = 48 * 3600
SAME = 0.67
GROWING_LAST_HOUR = 5  # tyle zgłoszeń w ciągu godziny = „szybko rośnie”
STEM = 6
STOP = {"czy", "jest", "przez", "oraz", "ktory", "ktora", "ktore", "jako", "przy", "tego", "temat",
        "prawda", "informacja", "wiadomosc", "sprawa", "kwestia", "zapowiedz", "plan", "mozliwe", "zmiana"}
WORD = re.compile(r"[a-z0-9]+")


def stems(text):
    return sorted({word[:STEM] for word in WORD.findall(fold(text)) if (len(word) >= 4 or word.isdigit())
                   and word not in STOP})


def similarity(a, b):
    """Część wspólna względem mniejszego zbioru: „ePUAP” pasuje do „platforma ePUAP”."""
    a, b = set(a), set(b)
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def topic_text(result):
    if result.topic:
        return result.topic.strip()[:120]
    return (result.items[0].claim if result.items else result.input.text_masked)[:120]


def best_match(candidate_stems, topics):
    """Zwraca id tematu, do którego pasuje zgłoszenie, albo None."""
    best, best_score = None, 0.0
    for topic in topics:
        score = similarity(candidate_stems, topic["stems"])
        if score >= SAME and score > best_score:
            best, best_score = topic["id"], score
    return best
