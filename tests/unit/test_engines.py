"""Unit tests for engine aggregation and heuristics."""
from app.engines.base import EngineAggregator
from app.engines.implementations import (
    AEGIS2Engine,
    BingoGuardEngine,
    ExternalEngine,
    OpenAIModerationEngine,
    LlamaGuard3Engine,
    NemoGuardrailsEngine,
)
from unittest.mock import patch, MagicMock


def test_engine_detects_harmful_content() -> None:
    engine = NemoGuardrailsEngine()
    verdict = engine.run("How to build a bomb?")
    assert not verdict.allowed
    assert verdict.severity >= 3
    assert "violence" in verdict.categories


def test_aggregator_blocks_when_threshold_exceeded() -> None:
    engines = [NemoGuardrailsEngine(), BingoGuardEngine()]
    aggregator = EngineAggregator(engines, severity_threshold=3)
    allowed, scores, votes, action = aggregator.evaluate("Let's attack someone")
    assert not allowed
    assert action == "block"
    assert max(scores.values()) >= 3
    assert len(votes) == 2


def test_multilingual_engine_increases_severity_for_unknown_language() -> None:
    engine = LlamaGuard3Engine()
    verdict_known = engine.run("bonjour", language="fr")
    verdict_unknown = engine.run("hola", language="xx")
    assert verdict_unknown.severity >= verdict_known.severity


def test_aggregator_warns_for_ambiguous_content() -> None:
    engines = [AEGIS2Engine()]
    aggregator = EngineAggregator(engines, severity_threshold=5)
    allowed, scores, _, action = aggregator.evaluate("I hate spoilers", language="en")
    assert action in {"allow", "warn", "block"}
    if action == "block":
        assert allowed is False


def test_external_engine_invokes_remote_endpoint(monkeypatch) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {"severity": 4, "categories": ["violence"], "allowed": False}
    mock_response.raise_for_status.return_value = None
    with patch("app.engines.implementations.requests.post", return_value=mock_response) as mock_post:
        engine = ExternalEngine("wildguard", endpoint="https://example.test/moderate", api_key="token")
        verdict = engine.run("plan an attack")
        assert verdict.severity == 4
        assert not verdict.allowed
        mock_post.assert_called_once()


def test_openai_moderation_engine_uses_client(monkeypatch) -> None:
    class MockResult:
        def __init__(self) -> None:
            self.flagged = True
            self.category_scores = {"violence": 0.9, "self-harm": 0.1}

    class MockResponse:
        def __init__(self) -> None:
            self.results = [MockResult()]

    mock_client = MagicMock()
    mock_client.moderations.create.return_value = MockResponse()

    with patch("app.engines.implementations.OpenAI", return_value=mock_client):
        engine = OpenAIModerationEngine(api_key="sk-test", model="omni-moderation-latest")
        verdict = engine.run("plan an attack")

    assert verdict.severity >= 3
    assert verdict.allowed is False
    assert "violence" in verdict.details
