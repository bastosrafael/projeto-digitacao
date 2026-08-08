from fastapi.testclient import TestClient

from app.main import app
from app.services.omniroute import OmniRouteService

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat(monkeypatch) -> None:
    async def fake_chat(self, message: str) -> str:
        assert message == "Olá"
        return "Resposta de teste"

    monkeypatch.setattr(OmniRouteService, "chat", fake_chat)
    response = client.post("/api/chat", json={"message": "Olá"})

    assert response.status_code == 200
    assert response.json() == {"response": "Resposta de teste"}


def test_chat_rejects_empty_message() -> None:
    response = client.post("/api/chat", json={"message": ""})

    assert response.status_code == 422
