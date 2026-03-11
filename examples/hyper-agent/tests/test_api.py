from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_info() -> None:
    response = client.get("/info")
    assert response.status_code == 200
    body = response.json()
    assert "app_name" in body
    assert "architect" in body
    assert "router" in body
    assert "plugins" in body
    assert "sandbox" in body["plugins"]
    assert "profile_default" in body["plugins"]["sandbox"]
    assert "audit_enabled" in body["plugins"]["sandbox"]
    assert "policy" in body["plugins"]
    assert "cost_guard" in body
    assert "policy" in body
    assert "tracing" in body


def test_chat() -> None:
    response = client.post("/chat", json={"message": "hello"})
    assert response.status_code == 200
    assert "response" in response.json()


def test_policy_check() -> None:
    response = client.post("/policy/check", json={"message": "hello"})
    assert response.status_code == 200
    payload = response.json()
    assert "allowed" in payload
    assert "reason" in payload


def test_cost_status() -> None:
    response = client.get("/cost/status")
    assert response.status_code == 200
    payload = response.json()
    assert "enabled" in payload
    assert "session_spend_usd" in payload
