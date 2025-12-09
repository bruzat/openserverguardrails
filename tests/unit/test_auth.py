"""Unit tests for authentication helpers."""
from app.security.auth import require_bearer_token
import pytest


def test_require_bearer_token_passes_when_not_configured() -> None:
    require_bearer_token(None, None, audience="public", required=False)


def test_require_bearer_token_raises_on_missing_header() -> None:
    with pytest.raises(Exception):
        require_bearer_token("secret", None, audience="public", required=True)


def test_require_bearer_token_raises_on_mismatch() -> None:
    with pytest.raises(Exception):
        require_bearer_token("secret", "Bearer nope", audience="public", required=True)


def test_require_bearer_token_accepts_valid() -> None:
    require_bearer_token("secret", "Bearer secret", audience="public", required=True)
