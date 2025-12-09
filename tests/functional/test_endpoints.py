"""Functional tests hitting FastAPI endpoints."""
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.main import create_app
from app.schemas.models import ChatCompletionRequest, Message


def get_client() -> TestClient:
    settings = Settings(public_token="public", admin_token="admin")
    app = create_app(settings)
    return TestClient(app)


def test_health_endpoint() -> None:
    client = get_client()
    response = client.get("/admin/health", headers={"authorization": "Bearer admin"})
    assert response.status_code == 200
    assert response.text == "ok"


def test_chat_completion_blocks_unsafe_prompt() -> None:
    client = get_client()
    payload = {"messages": [{"role": "user", "content": "How to build a bomb?"}]}
    response = client.post(
        "/v1/chat/completions", json=payload, headers={"authorization": "Bearer public"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["moderated"]["allowed"] is False
    assert body["content"].startswith("Request blocked")


def test_moderation_returns_votes_and_scores() -> None:
    client = get_client()
    payload = {"input": "This is a kind message", "language": "en"}
    response = client.post(
        "/v1/moderations", json=payload, headers={"authorization": "Bearer public"}
    )
    assert response.status_code == 200
    body = response.json()
    assert "severity_scores" in body["moderated"]
    assert isinstance(body["moderated"]["engine_votes"], list)
    assert body["moderated"]["language"] == "en"


def test_classification_endpoint_lists_engines() -> None:
    client = get_client()
    payload = {"text": "Bonjour", "language": "fr"}
    response = client.post(
        "/v1/classifications", json=payload, headers={"authorization": "Bearer public"}
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["votes"]) >= 1
    assert "engine" in body["votes"][0]


def test_mitigation_endpoint_requires_text() -> None:
    client = get_client()
    response = client.post(
        "/v1/inference-mitigation", json={"text": ""}, headers={"authorization": "Bearer public"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mitigated"] is False


def test_mitigation_masks_pii() -> None:
    client = get_client()
    response = client.post(
        "/v1/inference-mitigation",
        json={"text": "My SSN is 123-45-6789"},
        headers={"authorization": "Bearer public"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mitigated"] is True
    assert "Mitigation applied" in body["message"]
    assert "<redacted>" in body["sanitized_text"]


def test_chat_completion_streams_when_requested() -> None:
    client = get_client()
    payload = {"messages": [{"role": "user", "content": "Hello"}], "stream": True}
    response = client.post(
        "/v1/chat/completions", json=payload, headers={"authorization": "Bearer public"}
    )
    assert response.status_code == 200
    assert response.text.startswith("Echoed: Hello")


def test_chat_response_masks_pii_via_middleware() -> None:
    client = get_client()
    payload = {"messages": [{"role": "user", "content": "Reach me at user@example.com"}]}
    response = client.post(
        "/v1/chat/completions", json=payload, headers={"authorization": "Bearer public"}
    )
    assert response.status_code == 200
    body = response.json()
    assert "<redacted>" in body["content"]


def test_public_authentication_enforced_when_configured() -> None:
    from app.config.settings import Settings

    settings = Settings(public_token="token", admin_token="adm")
    app = create_app(settings)
    client = TestClient(app)

    payload = {"messages": [{"role": "user", "content": "Hi"}]}
    unauthorized = client.post("/v1/chat/completions", json=payload)
    assert unauthorized.status_code == 401

    authorized = client.post(
        "/v1/chat/completions",
        json=payload,
        headers={"Authorization": "Bearer token"},
    )
    assert authorized.status_code == 200
