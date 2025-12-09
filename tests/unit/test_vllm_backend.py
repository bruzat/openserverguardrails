"""Unit tests for the vLLM backend adapter."""

import pytest

from app.backends.llm import VLLMBackend
from app.schemas.models import Message


def test_vllm_backend_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    class FakeResponse:
        def __init__(self, payload: dict):
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self):
            return self._payload

    def fake_post(url, json=None, headers=None, timeout=None, stream=False):  # type: ignore[override]
        captured.update({"url": url, "json": json, "headers": headers, "timeout": timeout, "stream": stream})
        return FakeResponse({"choices": [{"message": {"content": "hello"}}]})

    monkeypatch.setattr("app.backends.llm.requests.post", fake_post)
    backend = VLLMBackend("https://vllm.test", api_key="key", model="mistral", chunk_size=4)
    output = backend.generate([Message(role="user", content="hi")], language="fr")
    assert output == "hello (fr)"
    assert captured["url"] == "https://vllm.test/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer key"
    assert captured["json"]["model"] == "mistral"
    assert captured["json"]["stream"] is False


def test_vllm_backend_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    events = [b"data: {\"choices\":[{\"delta\":{\"content\":\"abc\"}}]}\n", b"data: {\"choices\":[{\"delta\":{\"content\":\"def\"}}]}\n"]

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def iter_lines(self):
            yield from self.payload

    def fake_post(url, json=None, headers=None, timeout=None, stream=False):  # type: ignore[override]
        assert stream is True
        return FakeResponse(events)

    monkeypatch.setattr("app.backends.llm.requests.post", fake_post)
    backend = VLLMBackend("https://vllm.test", chunk_size=2)
    chunks = list(backend.stream([Message(role="user", content="hi")], language=None))
    assert chunks == ["abc", "def"]
