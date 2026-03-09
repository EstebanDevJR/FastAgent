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
    assert "plugins" in body


def test_chat() -> None:
    response = client.post("/chat", json={"message": "hello"})
    assert response.status_code == 200
    assert "response" in response.json()
