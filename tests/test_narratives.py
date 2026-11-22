from fastapi.testclient import TestClient

from app.core.service import get_service
from app.ingest import narratives
from app.main import create_app
from prawdowid_core import DEFAULT_CORPUS

MESSAGE = ("PILNE: 21.11.2026 Polska wkroczy na zachodnią Ukrainę i zajmie Lwów. "
           "Podpisano: Sztab Generalny Wojska Polskiego")


def test_recycled_narrative_shows_case_differences_and_keeps_verdict_on_evidence(monkeypatch, tmp_path):
    monkeypatch.setenv("PRAWDOWID_ENV", "development")
    monkeypatch.setenv("PRAWDOWID_EVALUATOR", "fake")
    monkeypatch.setenv("PRAWDOWID_CORPUS", str(DEFAULT_CORPUS.with_name("Prawdowid_Korpus_Probny.jsonl")))
    monkeypatch.setenv("PRAWDOWID_DATA_DIR", str(tmp_path))
    get_service.cache_clear()
    match = narratives.find(MESSAGE, narratives.load())[0]
    assert match["url"].startswith("https://euvsdisinfo.eu/report/")
    assert any("21.11.2026" in d for d in match["differences"])
    assert any("Lwów" in d for d in match["differences"])
    assert any("Sztab Generalny" in d for d in match["differences"])
    assert narratives.find("Czy RCB wysłało SMS o burzy?", narratives.load()) == []
    with TestClient(create_app()) as client:
        result = client.post("/api/v1/checks", json={"text": MESSAGE}).json()
    notice = next(n for n in result["notices"] if n["type"] == "known_narrative")
    assert notice["url"] == match["url"] and notice["label"] == match["narrative"]
    assert len(notice["text"]) < 140  # krótka etykieta, nie akapit
    # Podobieństwo nie jest dowodem: bez materiału o tej sprawie werdykt pozostaje wstrzymany.
    assert result["items"][0]["label"] == "insufficient_evidence"
    get_service.cache_clear()


def test_cached_result_does_not_duplicate_narrative_notice(monkeypatch, tmp_path):
    monkeypatch.setenv("PRAWDOWID_ENV", "development")
    monkeypatch.setenv("PRAWDOWID_EVALUATOR", "fake")
    monkeypatch.setenv("PRAWDOWID_CORPUS", str(DEFAULT_CORPUS.with_name("Prawdowid_Korpus_Probny.jsonl")))
    monkeypatch.setenv("PRAWDOWID_DATA_DIR", str(tmp_path))
    get_service.cache_clear()
    service = get_service()
    from app.contract import NoticeItem
    first = service.run(MESSAGE)
    stale = first.model_copy(update={"notices": [NoticeItem(type="known_narrative", text="stary długi akapit")]})
    service.store.cached = lambda key, now: stale
    from dataclasses import replace
    service.settings = replace(service.settings, evaluator="live", key="test")
    second = service.run(MESSAGE)
    narrative = [n for n in second.notices if n.type == "known_narrative"]
    assert second.meta.cached  # przebieg naprawdę przeszedł przez pamięć wyników
    assert len(narrative) == 1 and narrative[0].label
    get_service.cache_clear()
