"""Unit tests for the HuggingFace text generation backend."""
from types import SimpleNamespace

import pytest

from app.backends.llm import HuggingFaceTextGenBackend
from app.schemas.models import Message


def test_hf_backend_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeResponse:
        def __init__(self, payload: dict):
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return [self._payload]

    def fake_post(url, json=None, headers=None, timeout=None):  # type: ignore[override]
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse({"generated_text": "Bonjour"})

    monkeypatch.setattr("app.backends.llm.requests.post", fake_post)
    backend = HuggingFaceTextGenBackend("https://example.test", api_token="token", chunk_size=4)
    result = backend.generate([Message(role="user", content="Hi there")], language="fr")
    assert result == "Bonjour (fr)"
    assert captured["headers"]["Authorization"] == "Bearer token"
    assert captured["json"]["inputs"] == "Hi there"


def test_hf_backend_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return [{"generated_text": "Streamed text"}]

    monkeypatch.setattr("app.backends.llm.requests.post", lambda *args, **kwargs: FakeResponse())
    backend = HuggingFaceTextGenBackend("https://example.test", chunk_size=7)
    chunks = list(backend.stream([Message(role="user", content="Hi")], language=None))
    assert chunks == ["Streame", "d text"]
