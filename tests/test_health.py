from fastapi.testclient import TestClient

from pekua.api.app import create_app


def test_liveness() -> None:
    response = TestClient(create_app()).get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_workspace_ui_is_served_at_root() -> None:
    response = TestClient(create_app()).get("/")
    assert response.status_code == 200
    assert "Ask across science and patents" in response.text


def test_connector_status_requires_tenant_and_keeps_restricted_sources_disabled() -> None:
    client = TestClient(create_app())
    assert client.get("/api/v1/connectors").status_code == 422
    response = client.get("/api/v1/connectors", headers={"X-Tenant-ID": "test-tenant"})
    assert response.status_code == 200
    sources = {item["source_id"]: item for item in response.json()}
    assert sources["arxiv"]["can_execute"] is True
    assert sources["epo_ops"]["can_execute"] is False
    assert sources["ajol"]["can_execute"] is False
