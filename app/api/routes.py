"""API router definitions."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Response
from fastapi.responses import PlainTextResponse, StreamingResponse
from prometheus_client import generate_latest

from app.config.settings import Settings
from app.observability import metrics
from app.schemas.models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ClassificationRequest,
    ClassificationResponse,
    MitigationRequest,
    MitigationResponse,
    ModerationRequest,
    ModerationResponse,
)
from app.security.auth import admin_auth_dependency, public_auth_dependency
from app.services.chat import ChatService
from app.services.mitigation import MitigationService
from app.services.moderation import ModerationService


def _record(endpoint: str, status: str, start: float) -> None:
    duration = time.time() - start
    metrics.record(endpoint, status, duration)


def build_public_router(
    chat_service: ChatService, moderation_service: ModerationService, mitigation_service: MitigationService, settings: Settings
) -> APIRouter:
    api_router = APIRouter(
        dependencies=[Depends(public_auth_dependency(settings.public_token, required=settings.require_auth))]
    )

    @api_router.post("/chat/completions", response_model=ChatCompletionResponse)
    async def chat_completions(request: ChatCompletionRequest):
        start = time.time()
        if request.stream:
            stream = chat_service.generate_stream(request)
            _record("chat_completions", "stream", start)
            return StreamingResponse(stream, media_type="text/plain")
        response = chat_service.generate(request)
        _record("chat_completions", "success", start)
        return response

    @api_router.post("/moderations", response_model=ModerationResponse)
    async def moderate(request: ModerationRequest) -> ModerationResponse:
        start = time.time()
        moderated = moderation_service.moderate(request.input, language=request.language)
        _record("moderations", "success", start)
        return ModerationResponse(moderated=moderated)

    @api_router.post("/classifications", response_model=ClassificationResponse)
    async def classify(request: ClassificationRequest) -> ClassificationResponse:
        start = time.time()
        votes = moderation_service.classify(request.text, language=request.language)
        _record("classifications", "success", start)
        return ClassificationResponse(votes=votes)

    @api_router.post("/inference-mitigation", response_model=MitigationResponse)
    async def mitigation(request: MitigationRequest) -> MitigationResponse:
        start = time.time()
        if not request.text:
            _record("inference_mitigation", "no_text", start)
            return MitigationResponse(mitigated=False, message="No text provided")
        plan = mitigation_service.apply(request.text, language=request.language)
        status = "masked" if plan.masked_pii else "pass"
        _record("inference_mitigation", status, start)
        return MitigationResponse(
            mitigated=True, message=plan.message, sanitized_text=plan.sanitized_text
        )

    return api_router
def build_admin_router(settings: Settings) -> APIRouter:
    admin_router = APIRouter(
        dependencies=[Depends(admin_auth_dependency(settings.admin_token, required=settings.require_auth))]
    )

    @admin_router.get("/health", response_class=PlainTextResponse)
    async def health() -> str:
        return "ok"

    @admin_router.get("/metrics")
    async def metrics_endpoint() -> Response:
        return Response(generate_latest(), media_type="text/plain")

    return admin_router


__all__ = ["build_public_router", "build_admin_router"]
