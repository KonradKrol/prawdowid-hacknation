"""Deterministic development samples. Disabled by production configuration."""

from app.contract import ContextMismatch, Item, NoticeItem
from app.core.result import missing_item
from app.ingest.imgw import FEED, covers
from app.ingest.places import signature


def official_match(question, sources, received):
    found = signature(question, received)
    if found is None:
        return None
    return next((row for row in sources if row.get("feed") == FEED and covers(row, found)), None)


def demo_result(result, question, sources, make_evidence, received=None):
    value = question.casefold()
    official = official_match(question, sources, received) if received else None
    if "awaria" in value:
        result.status, result.message = "technical_error", "Symulowany błąd techniczny."
    elif "wiersz" in value:
        result.status, result.message = "out_of_scope", "Prawdowid sprawdza informacje publiczne."
    elif len(question) < 12:
        result.status = "needs_clarification"
        result.message = "Potrzebna jest dodatkowa informacja."
        result.clarification_question = "Którą wiadomość chcesz sprawdzić?"
    elif official is not None:
        result.items = [make_evidence(official, question, "supports", "confirmed")]
    elif "uważam" in value:
        result.items = [Item(id="t1", claim=question, kind="verdict", label="not_verifiable", reason="To opinia.")]
    elif "kiedy" in value and sources:
        dated = next((row for row in sources if row.get("published_on")), None)
        if dated:
            result.items = [make_evidence(dated, question, "supports", "answer")]
    elif "dziś" in value and sources:
        result.items = [make_evidence(sources[0], question, "context", "misleading")]
        result.items[0].context_mismatch = ContextMismatch(
            field="date", claim_value="dziś", source_value=sources[0].get("published_on") or "inna data",
            explanation="Próba różnicy daty."
        )
    elif "rcb" in value and any(row["id"] == "rcb-2018-dementi" for row in sources):
        row = next(row for row in sources if row["id"] == "rcb-2018-dementi")
        result.items = [make_evidence(row, "RCB wysłało SMS", "refutes", "false"),
                        missing_item("t2", "Liczba odbiorców", "Komunikat nie podaje liczby.",
                                     "Źródło podające liczbę odbiorców tej wiadomości.")]
    elif "liczba" in value and len(sources) >= 2:
        left = make_evidence(sources[0], question, "supports", "confirmed")
        right = make_evidence(sources[1], question, "refutes", "false")
        result.items = [missing_item("t1", question, "Materiały się różnią.", evidence=left.evidence + right.evidence)]
    if result.status == "ok" and not result.items:
        result.items = [missing_item("t1", question, "Przykład braku wystarczających dowodów.")]
    if "zignoruj" in value:
        result.notices.append(NoticeItem(type="instructions_ignored", text="Instrukcje ze zgłoszenia pominięto."))
    return result
