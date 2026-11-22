from app.config import Settings
from app.ingest import narrative_search, narratives


def test_semantic_candidate_requires_model_agreement(monkeypatch):
    case = narratives.load(narratives.DEFAULT_PATH)[0]
    vector = (1.0,) + (0.0,) * (narrative_search.DIMENSIONS - 1)
    monkeypatch.setattr(narrative_search, "load_index", lambda: {
        case["case_id"]: (narrative_search.case_digest(case), vector),
    })
    monkeypatch.setattr(narrative_search, "embeddings", lambda *args, **kwargs: [vector])
    matcher = narrative_search.NarrativeSearch(Settings(), [case])
    calls = []

    def compare(_model, _prompt, data, result_type, _budget):
        calls.append(data)
        return result_type(case_id=None if "kolej" in data["text"] else case["case_id"]), {}

    monkeypatch.setattr(matcher.provider, "complete", compare)
    paraphrase = "Warszawa zamierza odzyskać miasto Lwa"
    assert not narratives.find(paraphrase, [case])
    assert matcher.find(paraphrase) == case
    assert matcher.find(paraphrase) == case
    assert len(calls) == 1
    assert matcher.find("Czy powstanie kolej do Lwowa?") is None
