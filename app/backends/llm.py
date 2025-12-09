"""Lightweight LLM backend abstractions.

The project does not bundle heavyweight model dependencies; instead this module
provides a minimal interface along with a deterministic backend that simulates
generation and streaming. This allows the API surface to behave similarly to a
real model while keeping tests fast and hermetic. A best-effort OpenAI backend
is also provided so deployments with valid credentials can exercise a real
provider without code changes.
"""
from __future__ import annotations

import itertools
import json
from typing import Generator, Iterable, Protocol

import requests

try:  # Optional dependency; only imported when available
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency path
    OpenAI = None

from app.schemas.models import Message


class LLMBackend(Protocol):
    """Protocol describing a chat-oriented backend."""

    def generate(self, messages: Iterable[Message], *, language: str | None) -> str:
        """Generate a full completion for the conversation."""

    def stream(self, messages: Iterable[Message], *, language: str | None) -> Generator[str, None, None]:
        """Generate the completion as a stream of text chunks."""


class EchoLLMBackend:
    """Deterministic backend used for local and test runs.

    The backend concatenates user messages, annotates them with the target
    language, and emits the text either as a whole or in small chunks. Although
    simple, this abstraction mirrors the contract a real model backend would
    expose, making it straightforward to later plug in vLLM, OpenAI, or another
    provider without touching the higher-level services.
    """

    def __init__(self, *, chunk_size: int = 16) -> None:
        self.chunk_size = chunk_size

    def generate(self, messages: Iterable[Message], *, language: str | None) -> str:
        content = self._merge_messages(messages)
        suffix = f" ({language})" if language else ""
        return f"Echoed: {content}{suffix}"

    def stream(self, messages: Iterable[Message], *, language: str | None) -> Generator[str, None, None]:
        text = self.generate(messages, language=language)
        for start in range(0, len(text), self.chunk_size):
            yield text[start : start + self.chunk_size]

    @staticmethod
    def _merge_messages(messages: Iterable[Message]) -> str:
        user_contents = [message.content for message in messages if message.role == "user"]
        return " ".join(user_contents) or next(iter(itertools.chain(messages)), Message(role="user", content="", language=None)).content


class OpenAIChatBackend:
    """Backend proxying chat completions to the OpenAI API."""

    def __init__(self, api_key: str, *, model: str, base_url: str | None = None, chunk_size: int = 16) -> None:
        if OpenAI is None:
            raise ImportError("openai package is required for OpenAIChatBackend")
        if not api_key:
            raise ValueError("api_key is required for OpenAIChatBackend")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.chunk_size = chunk_size

    def generate(self, messages: Iterable[Message], *, language: str | None) -> str:
        payload = [self._to_payload(message) for message in messages]
        response = self.client.chat.completions.create(model=self.model, messages=payload)
        return (response.choices[0].message.content or "").strip()

    def stream(self, messages: Iterable[Message], *, language: str | None) -> Generator[str, None, None]:
        payload = [self._to_payload(message) for message in messages]
        stream = self.client.chat.completions.create(model=self.model, messages=payload, stream=True)
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    @staticmethod
    def _to_payload(message: Message) -> dict:
        return {"role": message.role, "content": message.content}


class HuggingFaceTextGenBackend:
    """Backend for Hugging Face text-generation-inference or Inference API.

    The backend performs a simple HTTP POST against a provided endpoint and
    expects a JSON payload with a "generated_text" field. This keeps the
    implementation lightweight while enabling deployments to plug in an actual
    hosted model without additional code changes. All network interactions are
    kept synchronous and small to avoid increasing test flakiness; functional
    tests mock the HTTP layer.
    """

    def __init__(self, endpoint: str, *, api_token: str | None = None, timeout: int = 30, chunk_size: int = 32) -> None:
        if not endpoint:
            raise ValueError("endpoint is required for HuggingFaceTextGenBackend")
        self.endpoint = endpoint
        self.api_token = api_token
        self.timeout = timeout
        self.chunk_size = chunk_size

    def generate(self, messages: Iterable[Message], *, language: str | None) -> str:
        text = EchoLLMBackend._merge_messages(messages)
        payload = {"inputs": text, "parameters": {"return_full_text": False}}
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        response = requests.post(self.endpoint, json=payload, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and data:
            generated = data[0].get("generated_text", "")
        elif isinstance(data, dict):
            generated = data.get("generated_text") or data.get("generated_texts", "")
        else:
            generated = ""
        suffix = f" ({language})" if language else ""
        return (generated or "").strip() + suffix

    def stream(self, messages: Iterable[Message], *, language: str | None) -> Generator[str, None, None]:
        text = self.generate(messages, language=language)
        for start in range(0, len(text), self.chunk_size):
            yield text[start : start + self.chunk_size]


class VLLMBackend:
    """Backend targeting vLLM's OpenAI-compatible HTTP API."""

    def __init__(
        self,
        endpoint: str,
        *,
        api_key: str | None = None,
        timeout: int = 30,
        model: str | None = None,
        chunk_size: int = 32,
    ) -> None:
        if not endpoint:
            raise ValueError("endpoint is required for VLLMBackend")
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.model = model
        self.chunk_size = chunk_size

    def generate(self, messages: Iterable[Message], *, language: str | None) -> str:
        payload = {
            "model": self.model,
            "messages": [self._to_payload(m) for m in messages],
            "stream": False,
        }
        response = self._post(payload)
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        suffix = f" ({language})" if language else ""
        return (content or "").strip() + suffix

    def stream(self, messages: Iterable[Message], *, language: str | None) -> Generator[str, None, None]:
        payload = {
            "model": self.model,
            "messages": [self._to_payload(m) for m in messages],
            "stream": True,
        }
        response = self._post(payload, stream=True)
        for line in response.iter_lines():
            if not line:
                continue
            if line.startswith(b"data: "):
                try:
                    data = line[len(b"data: ") :].decode("utf-8")
                    chunk = json.loads(data)
                except Exception:
                    continue
                delta = (
                    chunk.get("choices", [{}])[0]
                    .get("delta", {})
                    .get("content")
                )
                if delta:
                    yield delta

    def _post(self, payload: dict, *, stream: bool = False):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = requests.post(
            f"{self.endpoint}/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=self.timeout,
            stream=stream,
        )
        response.raise_for_status()
        return response

    @staticmethod
    def _to_payload(message: Message) -> dict:
        return {"role": message.role, "content": message.content}


__all__ = [
    "LLMBackend",
    "EchoLLMBackend",
    "OpenAIChatBackend",
    "HuggingFaceTextGenBackend",
    "VLLMBackend",
]
