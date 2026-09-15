from fastapi.testclient import TestClient

from pekua.api.app import app


def test_liveness_contract() -> None:
    response = TestClient(app).get("/health/live")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["version"]


def test_openapi_is_available_for_connector_and_job_contract_testing() -> None:
    response = TestClient(app).get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Pekua API"
