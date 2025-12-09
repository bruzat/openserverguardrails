"""Unit tests for the lightweight LLM backend abstraction."""
from app.backends.llm import EchoLLMBackend
from app.schemas.models import Message


def test_echo_backend_generates_with_language_suffix() -> None:
    backend = EchoLLMBackend(chunk_size=8)
    output = backend.generate([Message(role="user", content="hello", language="en")], language="fr")
    assert output.startswith("Echoed: hello")
    assert output.endswith("(fr)")


def test_echo_backend_streams_in_chunks() -> None:
    backend = EchoLLMBackend(chunk_size=5)
    chunks = list(
        backend.stream(
            [
                Message(role="user", content="hello", language="en"),
                Message(role="assistant", content="hi", language="en"),
            ],
            language=None,
        )
    )
    assert "".join(chunks).startswith("Echoed: hello")
    assert all(len(chunk) <= 5 for chunk in chunks)
