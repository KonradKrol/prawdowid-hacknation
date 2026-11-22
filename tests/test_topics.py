"""Grupowanie zgłoszeń w tematy: rdzenie słów, progi i przebieg do panelu moderatora."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core import topics
from app.core.service import get_service
from app.main import create_app
from prawdowid_core import DEFAULT_CORPUS


def test_same_subject_joins_and_different_ministers_do_not():
    msz = topics.stems("minister spraw zagranicznych")
    assert topics.similarity(msz, topics.stems("Minister Spraw Zagranicznych")) == 1.0
    assert topics.similarity(topics.stems("ePUAP"), topics.stems("platforma ePUAP")) == 1.0
    assert topics.similarity(msz, topics.stems("minister zdrowia")) < topics.SAME
    assert topics.best_match(topics.stems("minister zdrowia"), [{"id": 1, "stems": msz}]) is None


@pytest.fixture
def service(monkeypatch, tmp_path):
    monkeypatch.setenv("PRAWDOWID_ENV", "development")
    monkeypatch.setenv("PRAWDOWID_EVALUATOR", "fake")
    monkeypatch.setenv("PRAWDOWID_CORPUS", str(DEFAULT_CORPUS.with_name("Prawdowid_Korpus_Probny.jsonl")))
    monkeypatch.setenv("PRAWDOWID_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PRAWDOWID_ADMIN_TOKEN", "test-admin")
    get_service.cache_clear()
    yield get_service()
    get_service.cache_clear()


def test_reports_join_one_topic_and_panel_flags_growth(service):
    now = int(datetime.now(timezone.utc).timestamp())
    base = service.run("Czy RCB wysłało SMS?")
    texts = ["Sikorski odchodzi z rządu?", "Czy szef MSZ podał się do dymisji?", "Minister spraw zagranicznych zrezygnował?",
             "Słyszałem, że szef dyplomacji złożył dymisję", "Dymisja ministra spraw zagranicznych — prawda?"]
    ids = set()
    for text in texts:
        result = base.model_copy(update={"id": "chk_" + str(len(ids)) + text[:3], "topic": "dymisja ministra spraw zagranicznych",
                                         "subject": "minister spraw zagranicznych",
                                         "input": base.input.model_copy(update={"text_masked": text})})
        ids.add(service.register_topic(result, "web", now))
    other = base.model_copy(update={"id": "chk_other", "topic": "dymisja ministra zdrowia", "subject": "minister zdrowia"})
    other_id = service.register_topic(other, "web", now)
    assert len(ids) == 1 and other_id not in ids
    with TestClient(create_app()) as client:
        page = client.get("/moderacja", headers={"X-Admin-Token": "test-admin"}).text
    assert "dymisja ministra spraw zagranicznych" in page and "Szybko rośnie" in page
    assert page.count("Szybko rośnie") == 1  # temat ministra zdrowia ma jedno zgłoszenie


def test_old_topics_are_not_joined(service):
    now = int(datetime.now(timezone.utc).timestamp())
    base = service.run("Czy RCB wysłało SMS?")
    first = service.register_topic(base.model_copy(update={"topic": "blackout w całym kraju"}), "web", now - topics.WINDOW_S - 60)
    second = service.register_topic(base.model_copy(update={"topic": "blackout w całym kraju"}), "web", now)
    assert first != second
