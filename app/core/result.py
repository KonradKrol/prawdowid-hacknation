from datetime import date
import re

from app.contract import Evidence, Item, Premise, Strength
from app.core.safety import safe_copy
from prawdowid_core import literal_citation


POLISH_MONTHS = (
    "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
    "lipca", "sierpnia", "września", "października", "listopada", "grudnia",
)


def matches_publication_date(answer, published_on):
    if not answer or not published_on:
        return False
    if answer == published_on:
        return True
    publication = date.fromisoformat(published_on)
    human_date = f"{publication.day} {POLISH_MONTHS[publication.month - 1]} {publication.year}"
    normalized = " ".join(answer.casefold().split()).rstrip(".")
    return normalized in {human_date, f"{human_date} r", f"{human_date} roku", publication.strftime("%d.%m.%Y")}


# ---------- strażnik liczb i dat ----------
# Tekst modelu (reason, explanation, answer) jest tylko opisem. Każda liczba lub data,
# którą w nim podaje, musi występować w zweryfikowanym cytacie, dacie publikacji
# albo w pytaniu użytkownika. Zdanie z liczbą bez pokrycia usuwamy.
NUMBER = re.compile(r"\d+(?:[  .,]\d+)*")
SENTENCE = re.compile(r"(?<=[.!?])\s+")


def _forms(raw):
    """'207,9' → {'207.9'}, '1 000' / '1.000' → {'1000', '1.000'}, '21.11.2026' → też '21','11','2026'."""
    compact = re.sub(r"[  ]", "", raw).rstrip(".,").replace(",", ".")
    parts = [p for p in compact.split(".") if p]
    return compact, {compact, "".join(parts)}, parts


def numbers_in(text):
    found = set()
    for raw in NUMBER.findall(text or ""):
        _, forms, parts = _forms(raw)
        found |= forms | set(parts)
    return {n.lstrip("0") or "0" for n in found}


def allowed_numbers(evidence, question):
    allowed = numbers_in(question)
    for row in evidence:
        allowed |= numbers_in(row.quote)
        if row.published_on:
            for part in row.published_on.split("-"):  # 2024-04-05 → 2024, 4, 5
                allowed |= numbers_in(part)
    return allowed


def unsupported(text, allowed):
    """Liczby z tekstu bez pokrycia w materiale. Liczba dziesiętna (207,9) musi wystąpić w całości;
    data zapisana z kropkami (21.11.2026) przechodzi, gdy każda jej część jest w materiale."""
    out = set()
    for raw in NUMBER.findall(text or ""):
        compact, forms, parts = _forms(raw)
        if {f.lstrip("0") or "0" for f in forms} & allowed:
            continue
        if len(parts) >= 3 and all((p.lstrip("0") or "0") in allowed for p in parts):
            continue
        out.add(compact)
    return out


def guard_numbers(text, allowed):
    """Zwraca tekst bez zdań zawierających liczby bez pokrycia (albo None, gdy nic nie zostało)."""
    if not text:
        return text
    kept = [s for s in SENTENCE.split(text.strip()) if not unsupported(s, allowed)]
    return " ".join(kept) or None


def citations_for(draft, sources):
    evidence = []
    for ref in draft.evidence[:8]:
        source = next((row for row in sources if row["id"] == ref.source_id), None)
        if source is None:
            continue
        published = source.get("published_on")
        if ref.field == "published_on":
            if (draft.kind != "answer" or ref.quote is not None or ref.stance != "supports"
                    or not matches_publication_date(draft.answer, published)):
                continue
        elif not ref.quote or len(ref.quote.split()) < 3 or not literal_citation([source], ref.source_id, ref.quote):
            continue
        entry = Evidence(
            source_id=source["id"], stance=ref.stance, field=ref.field, quote=ref.quote,
            title=source["title"], publisher=source["publisher"], url=source["url"],
            published_on=published, retrieved_on=source["checked_on"], source_type=source["type"],
            is_primary=source["type"] in {"urzędowe", "samorządowe", "pierwotne", "dane_publiczne", "dane publiczne"},
            archival=bool(source.get("archival")) or bool(published and
                int(source["checked_on"][:4]) - int(published[:4]) >= 2),
            explanation=getattr(ref, "explanation", None) or None,
        )
        if entry not in evidence:
            evidence.append(entry)
    return evidence


def strength_of(label, evidence, mismatch):
    if label in {"insufficient_evidence", "not_verifiable"} or not evidence:
        return Strength()
    primary = any(row.is_primary and row.field == "excerpt" for row in evidence)
    points = 3 if primary else 2
    premises = [Premise(code="primary_source", text="Bezpośredni cytat ze źródła pierwotnego.", effect="plus")] if primary else []
    publishers = {row.publisher for row in evidence}
    if len(publishers) >= 2:
        points += 1
        premises.append(Premise(code="multiple_publishers", text="Dowody wskazali różni wydawcy.", effect="plus"))
    elif not any(row.is_primary for row in evidence):
        points -= 1
        premises.append(Premise(code="single_secondary", text="Podstawa to jedno źródło wtórne.", effect="minus"))
    if mismatch and all(row.stance == "context" for row in evidence):
        points -= 1
        premises.append(Premise(code="context_only", text="Dowody wyjaśniają przede wszystkim kontekst.", effect="minus"))
    return Strength(level="strong" if points >= 4 else "moderate" if points == 3 else "weak", premises=premises)


def missing_item(item_id, claim, reason, missing=None, evidence=None, span=None):
    return Item(id=item_id, claim=claim, claim_span=span, kind="verdict",
                label="insufficient_evidence", reason=reason,
                missing_evidence=missing or "Potrzebne jest źródło odnoszące się bezpośrednio do tej sytuacji.",
                evidence=evidence or [])


def normalize(draft, sources, item_id, question, canary):
    claim = safe_copy(draft.claim, canary)
    span = safe_copy(draft.claim_span, canary)
    if not span or span not in question:
        span = None
    reason = safe_copy(draft.reason, canary)
    answer = safe_copy(draft.answer, canary)
    missing = safe_copy(draft.missing_evidence, canary)
    mismatch = draft.context_mismatch
    if mismatch is not None:
        mismatch = mismatch.model_copy(update={
            name: safe_copy(getattr(mismatch, name), canary)
            for name in ("claim_value", "source_value", "explanation")
        })
    # Inspect all proposed quotes even when the code rejects them below.
    for ref in draft.evidence:
        safe_copy(ref.quote, canary)
        if getattr(ref, "explanation", None):
            ref.explanation = safe_copy(ref.explanation, canary)
    evidence = citations_for(draft, sources)
    allowed = allowed_numbers(evidence, question)
    if reason and unsupported(reason, allowed):
        reason = guard_numbers(reason, allowed) or "Szczegóły podajemy w cytacie ze źródła poniżej."
    evidence = [row.model_copy(update={"explanation": guard_numbers(row.explanation, allowed)})
                if row.explanation else row for row in evidence]
    if draft.label == "not_verifiable" and draft.kind == "verdict":
        return Item(id=item_id, claim=claim, claim_span=span, kind="verdict",
                    label="not_verifiable", reason=reason or "To opinia lub ocena.",
                    evidence=[row for row in evidence if row.stance == "context"])
    stances = {row.stance for row in evidence}
    if {"supports", "refutes"} <= stances:
        return missing_item(item_id, claim, "Źródła podają sprzeczne informacje.",
                            missing or "Potrzebny jest dowód rozstrzygający rozbieżność.", evidence, span)
    if draft.label == "insufficient_evidence":
        return missing_item(item_id, claim, reason or "Dostępne źródła nie rozstrzygają tej tezy.", missing, evidence, span)
    expected = {"confirmed": {"supports"}, "false": {"refutes"}, "misleading": {"context", "refutes"}}
    if draft.kind == "answer":
        answer = next((row.published_on for row in evidence if row.field == "published_on"), answer)
        # Krótka odpowiedź z liczbą bez pokrycia nie przechodzi — lepiej „Nie wiadomo” niż zmyślona liczba.
        valid = draft.label is None and bool(answer) and "supports" in stances and not unsupported(answer, allowed)
    else:
        valid = bool(stances & expected.get(draft.label, set()))
        if draft.label == "misleading":
            valid = valid and mismatch is not None and all(
                (mismatch.claim_value, mismatch.source_value, mismatch.explanation)
            )
        answer = None
    if not valid or len(evidence) < len(draft.evidence):
        return missing_item(item_id, claim, "Nie udało się zweryfikować podstawy odpowiedzi.", missing, span=span)
    return Item(id=item_id, claim=claim, claim_span=span, kind=draft.kind, label=draft.label,
                answer=answer, reason=reason, evidence=evidence, context_mismatch=mismatch,
                strength=strength_of(draft.label, evidence, mismatch))
