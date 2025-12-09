"""Unit tests for the OpenAI backend wrapper."""
from types import SimpleNamespace

import pytest

from app.backends import llm
from app.backends.llm import OpenAIChatBackend
from app.schemas.models import Message


class _FakeStream:
    def __iter__(self):
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="He"))])
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="llo"))])


class _FakeChatCompletions:
    def __init__(self, *, content: str):
        self._content = content
        self.stream_requests = []

    def create(self, *, model: str, messages: list[dict], stream: bool | None = None):
        if stream:
            self.stream_requests.append((model, messages))
            return _FakeStream()
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self._content))])


class _FakeClient:
    def __init__(self, *, content: str):
        self.chat = SimpleNamespace(completions=_FakeChatCompletions(content=content))


def _install_fake_client(monkeypatch: pytest.MonkeyPatch, content: str) -> None:
    def _factory(api_key: str, base_url: str | None = None):
        assert api_key == "secret"
        return _FakeClient(content=content)

    monkeypatch.setattr(llm, "OpenAI", _factory)


def test_openai_backend_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_client(monkeypatch, "Hello")
    backend = OpenAIChatBackend(api_key="secret", model="test-model")
    result = backend.generate([Message(role="user", content="Hi")], language="en")
    assert result == "Hello"


def test_openai_backend_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_client(monkeypatch, "Hello")
    backend = OpenAIChatBackend(api_key="secret", model="test-model")
    chunks = list(backend.stream([Message(role="user", content="Hi")], language=None))
    assert "".join(chunks) == "Hello"
