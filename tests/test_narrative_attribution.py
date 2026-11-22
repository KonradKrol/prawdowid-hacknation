from fastapi.testclient import TestClient
from app.core.service import get_service
from app.main import create_app


def test_narrative_attribution_only_appears_for_verified_case(monkeypatch, tmp_path):
    monkeypatch.setenv("PRAWDOWID_ENV", "development")
    monkeypatch.setenv("PRAWDOWID_EVALUATOR", "fake")
    monkeypatch.setenv("PRAWDOWID_DATA_DIR", str(tmp_path))
    get_service.cache_clear()
    with TestClient(create_app()) as client:
        confirmed = client.post("/sprawdz", data={"text": "Czy nazistowska Ukraina zaatakowała Rosję?"})
        assert confirmed.status_code == 200
        assert "EUvsDisinfo udokumentowało tę narrację w rosyjskim medium państwowym TASS." in confirmed.text
        assert "Co to znaczy?" in confirmed.text
        unverified = client.post("/sprawdz", data={"text": "Czy Polska chce zająć Lwów?"})
        assert unverified.status_code == 200
        assert "Uwaga: znana narracja dezinformacyjna" in unverified.text
        assert "w rosyjskim medium państwowym" not in unverified.text
