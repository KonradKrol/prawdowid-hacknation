from app.contract import Evidence, Item, Premise, Strength
from app.core.safety import safe_copy
from prawdowid_core import literal_citation


def citations_for(draft, sources):
    evidence = []
    for ref in draft.evidence[:8]:
        source = next((row for row in sources if row["id"] == ref.source_id), None)
        if source is None:
            continue
        published = source.get("published_on")
        if ref.field == "published_on":
            if (draft.kind != "answer" or published is None or draft.answer != published
                    or ref.quote is not None or ref.stance != "supports"):
                continue
        elif not ref.quote or len(ref.quote.split()) < 3 or not literal_citation([source], ref.source_id, ref.quote):
            continue
        entry = Evidence(
            source_id=source["id"], stance=ref.stance, field=ref.field, quote=ref.quote,
            title=source["title"], publisher=source["publisher"], url=source["url"],
            published_on=published, retrieved_on=source["checked_on"], source_type=source["type"],
            is_primary=source["type"] in {"urzędowe", "pierwotne", "dane_publiczne"},
            archival=bool(source.get("archival")) or bool(published and
                int(source["checked_on"][:4]) - int(published[:4]) >= 2),
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
    evidence = citations_for(draft, sources)
    if draft.label == "not_verifiable" and draft.kind == "verdict":
        return Item(id=item_id, claim=claim, claim_span=span, kind="verdict",
                    label="not_verifiable", reason=reason or "To opinia lub ocena.")
    stances = {row.stance for row in evidence}
    if {"supports", "refutes"} <= stances:
        return missing_item(item_id, claim, "Źródła podają sprzeczne informacje.",
                            missing or "Potrzebny jest dowód rozstrzygający rozbieżność.", evidence, span)
    if draft.label == "insufficient_evidence":
        return missing_item(item_id, claim, "Dostępne źródła nie rozstrzygają tej tezy.", missing, evidence, span)
    expected = {"confirmed": {"supports"}, "false": {"refutes"}, "misleading": {"context", "refutes"}}
    if draft.kind == "answer":
        valid = draft.label is None and bool(answer) and "supports" in stances
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
