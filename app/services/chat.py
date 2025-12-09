"""Chat service orchestrating moderation and response selection."""
from __future__ import annotations

from typing import Iterable, Optional

from app.backends.llm import LLMBackend
from app.schemas.models import ChatCompletionRequest, ChatCompletionResponse
from app.services.moderation import ModerationService
from app.services.mitigation import MitigationService


class ChatService:
    """Simple chat service that moderates and echoes user intent safely."""

    def __init__(
        self,
        moderation_service: ModerationService,
        *,
        backend: LLMBackend,
        mitigation_service: MitigationService | None = None,
    ) -> None:
        self.moderation_service = moderation_service
        self.backend = backend
        self.mitigation = mitigation_service or MitigationService()

    def generate(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        user_message = self._extract_user_message(request)
        moderated = self.moderation_service.moderate(user_message, language=request.language)
        if not moderated.allowed:
            content = "Request blocked due to safety policy."
        elif moderated.action == "warn":
            content = "Content may be sensitive. Proceeding with caution."
        else:
            content = self.backend.generate(request.messages, language=moderated.language or request.language)
        mitigated = self.mitigation.apply(content, language=moderated.language)
        return ChatCompletionResponse(content=mitigated.sanitized_text, moderated=moderated)

    def generate_stream(self, request: ChatCompletionRequest) -> Iterable[str]:
        """Stream the generated content chunk by chunk."""

        user_message = self._extract_user_message(request)
        moderated = self.moderation_service.moderate(user_message, language=request.language)
        if not moderated.allowed:
            yield "Request blocked due to safety policy."
            return
        if moderated.action == "warn":
            yield "Content may be sensitive. Proceeding with caution."
            return
        for chunk in self.backend.stream(request.messages, language=moderated.language or request.language):
            yield self.mitigation.apply(chunk, language=moderated.language).sanitized_text

    @staticmethod
    def _extract_user_message(request: ChatCompletionRequest) -> str:
        fallback: Optional[str] = None
        for message in reversed(request.messages):
            if message.role == "user":
                return message.content
            fallback = message.content
        return fallback or ""
