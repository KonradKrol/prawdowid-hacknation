"""Teksty interfejsu. Na razie tylko polski; klucze są gotowe pod en i uk."""

LABELS = {
    "pl": {
        "confirmed": {"name": "Potwierdzone", "icon": "check", "tone": "ok",
                      "hint": "Wiarygodne źródło potwierdza tę informację."},
        "false": {"name": "Fałszywe", "icon": "cross", "tone": "false",
                  "hint": "Wiarygodne źródło zaprzecza tej informacji."},
        "misleading": {"name": "Wprowadzające w błąd", "icon": "alert", "tone": "mislead",
                       "hint": "Prawdziwy materiał w złym czasie, miejscu albo kontekście."},
        "insufficient_evidence": {"name": "Brak wystarczających dowodów", "icon": "question", "tone": "nei",
                                  "hint": "W sprawdzonych źródłach nie znaleźliśmy niczego, co to rozstrzyga. Mówimy, czego brakuje."},
        "not_verifiable": {"name": "Nie podlega weryfikacji", "icon": "speech", "tone": "nv",
                           "hint": "To opinia, ocena albo prognoza, a nie fakt do sprawdzenia."},
        "answer": {"name": "Odpowiedź", "icon": "info", "tone": "answer",
                   "hint": "Odpowiedź na pytanie, oparta na źródle."},
    }
}

# Proste słowa dla obywatela; oficjalna klasa briefu jest w szczegółach oceny.
PLAIN = {
    "pl": {"confirmed": "Prawda", "false": "Nieprawda", "misleading": "Wprowadza w błąd",
           "insufficient_evidence": "Brak potwierdzenia", "not_verifiable": "Nie do sprawdzenia", "answer": "Odpowiedź"}
}

STATUSES = {
    "pl": {
        "needs_clarification": {"name": "Potrzebujemy jednej informacji, żeby to sprawdzić", "icon": "question"},
        "out_of_scope": {"name": "W tej sprawie nie możemy pomóc", "icon": "stop"},
        "invalid_input": {"name": "Nie możemy przyjąć tego tekstu", "icon": "alert"},
        "rate_limited": {"name": "Za dużo sprawdzeń naraz. Spróbuj za chwilę", "icon": "clock"},
        "technical_error": {"name": "Nie udało się sprawdzić wiadomości", "icon": "wrench"},
    }
}

STRENGTH = {
    "pl": {
        "strong": ("Mocna", 3),
        "moderate": ("Umiarkowana", 2),
        "weak": ("Słaba", 1),
        "none": ("Brak podstawy", 0),
    }
}

STANCE = {
    "pl": {"supports": "Potwierdza", "refutes": "Zaprzecza", "context": "Daje kontekst"}
}

MISMATCH_FIELD = {
    "pl": {"date": "Data", "place": "Miejsce", "person": "Osoba", "number": "Liczba",
           "scope": "Zakres", "source": "Nadawca"}
}

NOTICE_ICON = {
    "archival_material": "clock",
    "instructions_ignored": "shield",
    "partial_check": "info",
    "known_narrative": "link",
    "source_status": "info",
}

MONTHS = {
    "pl": ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca",
           "sierpnia", "września", "października", "listopada", "grudnia"]
}


def pl_count(n: int, one: str, few: str, many: str) -> str:
    if n == 1:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many
