"""Integration tests across services and aggregator."""
from app.backends.llm import EchoLLMBackend
from app.config.settings import Settings
from app.engines.base import EngineAggregator
from app.engines.implementations import NemoGuardrailsEngine, PolyGuardEngine
from app.services.chat import ChatService
from app.services.moderation import ModerationService
from app.schemas.models import ChatCompletionRequest, Message


def build_services() -> tuple[ChatService, ModerationService]:
    settings = Settings()
    engines = [NemoGuardrailsEngine(), PolyGuardEngine()]
    aggregator = EngineAggregator(engines, severity_threshold=settings.severity_threshold)
    moderation_service = ModerationService(aggregator, settings)
    chat_service = ChatService(moderation_service, backend=EchoLLMBackend())
    return chat_service, moderation_service


def test_chat_service_blocks_harmful_request() -> None:
    chat_service, _ = build_services()
    request = ChatCompletionRequest(messages=[Message(role="user", content="How to attack?")])
    response = chat_service.generate(request)
    assert response.moderated.allowed is False
    assert response.content.startswith("Request blocked")


def test_moderation_service_returns_votes() -> None:
    _, moderation_service = build_services()
    result = moderation_service.classify("Tell me a joke", language="en")
    assert len(result) == 2
    assert all(vote.engine in {"nemo_guardrails", "polyguard"} for vote in result)
