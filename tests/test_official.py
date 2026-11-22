"""Najważniejszy przebieg od początku do końca: zgłoszenia → sprawy → import IMGW → propozycja dla moderatora."""

from datetime import datetime
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.service import get_service
from app.ingest.places import WARSAW, signature
from app.main import create_app
from prawdowid_core import DEFAULT_CORPUS

FIXTURES = Path(__file__).parent / "fixtures"
SAME_EVENT = (
    "Uwaga, 3 grudnia 2026 w powiecie bytowskim będzie gołoledź na drogach!",
    "Słyszałem, że w pow. bytowskim 3.12.2026 drogi pokryje oblodzenie. Prawda?",
)
OTHER_COUNTY = "3 grudnia 2026 oblodzenie w powiecie chojnickim, jedźcie ostrożnie"
OTHER_DAY = "4 grudnia 2026 gołoledź w powiecie bytowskim"


def feed(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("PRAWDOWID_ENV", "development")
    monkeypatch.setenv("PRAWDOWID_EVALUATOR", "fake")
    monkeypatch.setenv("PRAWDOWID_CORPUS", str(DEFAULT_CORPUS.with_name("Prawdowid_Korpus_Probny.jsonl")))
    monkeypatch.setenv("PRAWDOWID_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PRAWDOWID_ADMIN_TOKEN", "test-admin")
    monkeypatch.delenv("PRAWDOWID_OFFICIAL_POLL_S", raising=False)
    monkeypatch.delenv("PRAWDOWID_WEB_FIXTURES", raising=False)
    get_service.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_service.cache_clear()


def test_signature_groups_same_event_and_splits_county_or_day():
    received = datetime(2026, 12, 1, 12, tzinfo=WARSAW)
    first, second = (signature(text, received) for text in SAME_EVENT)
    assert first.key == second.key == "oblodzenie|2201|2026-12-03"
    assert signature(OTHER_COUNTY, received).key == "oblodzenie|2202|2026-12-03"
    assert signature(OTHER_DAY, received).key == "oblodzenie|2201|2026-12-04"
    assert signature("Czy RCB wysłało SMS?", received) is None


def test_moderation_end_to_end(client):
    admin = {"X-Admin-Token": "test-admin"}
    for text in (*SAME_EVENT, OTHER_COUNTY, OTHER_DAY):
        assert client.post("/api/v1/checks", json={"text": text}).json()["status"] == "ok"
    # Przez adapter WhatsApp trafia do tej samej sprawy.
    client.post("/api/whatsapp/demo", json={"text": "Gołoledź w powiecie bytowskim 3 grudnia 2026?"})

    cases = {case["key"]: case for case in client.get("/api/v1/cases", headers=admin).json()["cases"]}
    assert set(cases) == {"oblodzenie|2201|2026-12-03", "oblodzenie|2202|2026-12-03", "oblodzenie|2201|2026-12-04"}
    main = cases["oblodzenie|2201|2026-12-03"]
    assert main["reports"] == 3
    assert "powiat bytowski" in main["missing"] and "IMGW" in main["missing"]
    assert main["last_result"]["label"] == "insufficient_evidence"
    assert cases["oblodzenie|2202|2026-12-03"]["reports"] == 1

    service = get_service()
    documents = len(service.corpus.sources)

    # 1. Komunikat bez związku ze sprawami: wpis trafia do korpusu, propozycji brak.
    first = service.official.sync(raw=feed("imgw_demo_1_bez_sprawy.json"))
    assert (first["status"], first["new"], first["proposals"]) == ("ok", 1, 0)

    # 2. Nowe ostrzeżenie o oblodzeniu: propozycja tylko w sprawie, której dotyczy.
    second = service.official.sync(raw=feed("imgw_demo_2_nowy.json"))
    assert (second["new"], second["unchanged"], second["proposals"]) == (1, 1, 1)
    board = {case["key"]: case for case in client.get("/api/v1/cases", headers=admin).json()["cases"]}
    proposal = board["oblodzenie|2201|2026-12-03"]["pending"][0]
    assert proposal["previous"]["label"] == "insufficient_evidence"
    assert proposal["proposed"]["label"] == "confirmed"
    assert proposal["quote"].startswith("Prognozuje się zamarzanie mokrej nawierzchni")
    assert proposal["version"] == 1
    assert board["oblodzenie|2202|2026-12-03"]["proposals"] == []
    assert board["oblodzenie|2201|2026-12-04"]["proposals"] == []

    # 3. Ponowny import tego samego wpisu: bez duplikatów wpisów, wersji, propozycji i dokumentów.
    again = service.official.sync(raw=feed("imgw_demo_2_nowy.json"))
    assert (again["new"], again["changed"], again["unchanged"], again["proposals"]) == (0, 0, 2, 0)
    status = client.get("/api/v1/official/status").json()
    assert (status["entries"], status["versions"]) == (2, 2)
    assert len(service.corpus.sources) == documents + 2
    assert len(client.get("/api/v1/cases", headers=admin).json()["cases"][0]["proposals"]) <= 1

    # 4. Strona moderatora pokazuje poprzedni wynik, propozycję i cytat.
    page = client.get("/moderacja", headers=admin).text
    assert "Poprzedni wynik" in page and "Proponowany wynik" in page and "zamarzanie mokrej nawierzchni" in page
    assert page.count('data-proposal="') == 1

    # 5. Korekta tego samego wpisu: nowa wersja zastępuje starą w indeksie i daje nową propozycję.
    corrected = service.official.sync(raw=feed("imgw_demo_3_korekta.json"))
    assert (corrected["changed"], corrected["proposals"]) == (1, 1)
    assert "imgw-Sk20261202140022222-v1" not in service.corpus.sources
    assert "imgw-Sk20261202140022222-v2" in service.corpus.sources
    assert len(service.corpus.sources) == documents + 2

    # 6. Decyzja moderatora zamyka sprawę.
    pending = client.get("/api/v1/cases", headers=admin).json()["cases"]
    main = next(case for case in pending if case["key"] == "oblodzenie|2201|2026-12-03")
    for item in main["pending"]:
        client.post(f"/api/v1/proposals/{item['id']}?decision=accept", headers=admin)
    main = next(case for case in client.get("/api/v1/cases", headers=admin).json()["cases"]
                if case["key"] == "oblodzenie|2201|2026-12-03")
    assert main["status"] == "resolved" and main["last_result"]["label"] == "confirmed"


def test_failed_sync_is_reported(client):
    service = get_service()

    def broken():
        raise OSError("IMGW HTTP 503")

    service.official.fetcher = broken
    summary = service.official.sync()
    assert summary["status"] == "error" and "503" in summary["error"]
    health = client.get("/health").json()["official_feed"]
    assert health["failing"] is True and "503" in health["last_error"]
    page = client.get("/moderacja", headers={"X-Admin-Token": "test-admin"}).text
    assert 'data-sync="failed"' in page and "Synchronizacja IMGW nie powiodła się" in page


def test_moderation_requires_token(client):
    assert client.get("/moderacja").status_code == 404
    assert client.get("/api/v1/cases").status_code == 404
    assert client.post("/api/v1/official/sync").status_code == 404
