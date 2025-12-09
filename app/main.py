"""FastAPI application entrypoint for the guardrails server."""
from __future__ import annotations

import logging
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import build_admin_router, build_public_router
from app.backends.llm import (
    EchoLLMBackend,
    HuggingFaceTextGenBackend,
    OpenAIChatBackend,
    VLLMBackend,
)
from app.config.settings import Settings, get_settings
from app.engines.base import EngineAggregator
from app.engines.implementations import ENGINE_REGISTRY, ExternalEngine
from app.middleware.circuit_breaker import CircuitBreaker
from app.middleware.pii_masking import PIIMaskingMiddleware
from app.observability.tracing import (
    emit_feedback,
    initialize_phoenix,
    initialize_tracing,
    initialize_trulens,
)
from app.services.chat import ChatService
from app.services.mitigation import MitigationService
from app.services.moderation import ModerationService

logger = logging.getLogger(__name__)


def create_engine_chain(
    engine_names: List[str],
    *,
    endpoints: dict[str, str] | None = None,
    api_keys: dict[str, str] | None = None,
    settings: Settings | None = None,
) -> List:
    """Instantiate engine classes from their registry keys.

    When an endpoint is provided for a given engine, a lightweight external adapter is
    created that can call the configured HTTP service instead of the heuristic fallback.
    """

    engines = []
    for name in engine_names:
        engine_cls = ENGINE_REGISTRY.get(name)
        if not engine_cls:
            logger.warning("Unknown engine %s skipped", name)
            continue
        if endpoints and name in endpoints:
            engines.append(
                ExternalEngine(
                    name=name,
                    endpoint=endpoints[name],
                    api_key=(api_keys or {}).get(name),
                    severity_bias=getattr(engine_cls(), "severity_bias", 0),
                )
            )
        else:
            try:
                engines.append(engine_cls(settings=settings) if settings else engine_cls())
            except TypeError:
                # Engines that do not accept settings keep default ctor
                engines.append(engine_cls())
    return engines


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure a FastAPI application instance."""

    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)

    initialize_tracing(settings.telemetry_enabled)
    initialize_trulens(settings.trulens_enabled)
    initialize_phoenix(settings.phoenix_enabled)

    if settings.require_auth and (not settings.public_token or not settings.admin_token):
        raise ValueError("public_token and admin_token must be set when require_auth is enabled")

    engines = create_engine_chain(
        settings.default_engine_chain,
        endpoints=settings.engine_endpoints,
        api_keys=settings.engine_api_keys,
        settings=settings,
    )
    aggregator = EngineAggregator(
        engines,
        severity_threshold=settings.severity_threshold,
        severity_action_map=settings.severity_action_map,
        category_action_overrides=settings.category_action_overrides,
    )
    if settings.default_backend == "openai":
        if not settings.openai_api_key:
            raise ValueError("openai_api_key must be configured when using the OpenAI backend")
        backend = OpenAIChatBackend(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
            chunk_size=settings.streaming_chunk_size,
        )
    elif settings.default_backend == "huggingface":
        if not settings.hf_endpoint:
            raise ValueError("hf_endpoint must be configured when using the HuggingFace backend")
        backend = HuggingFaceTextGenBackend(
            settings.hf_endpoint,
            api_token=settings.hf_api_token,
            chunk_size=settings.streaming_chunk_size,
        )
    elif settings.default_backend == "vllm":
        if not settings.vllm_endpoint:
            raise ValueError("vllm_endpoint must be configured when using the vLLM backend")
        backend = VLLMBackend(
            settings.vllm_endpoint,
            api_key=settings.vllm_api_key,
            model=settings.vllm_model,
            chunk_size=settings.streaming_chunk_size,
        )
    else:
        backend = EchoLLMBackend(chunk_size=settings.streaming_chunk_size)
    mitigation_service = MitigationService()
    moderation_service = ModerationService(aggregator, settings)
    chat_service = ChatService(moderation_service, backend=backend, mitigation_service=mitigation_service)

    app = FastAPI(title=settings.app_name)

    if settings.allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allow_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.add_middleware(
        CircuitBreaker,
        enabled=settings.enable_circuit_breaker,
        failure_threshold=settings.circuit_breaker_failures,
        reset_after_seconds=settings.circuit_breaker_reset_seconds,
    )
    app.add_middleware(PIIMaskingMiddleware)

    public_router = build_public_router(chat_service, moderation_service, mitigation_service, settings)
    admin_router = build_admin_router(settings)

    app.include_router(public_router, prefix=settings.api_v1_prefix)
    app.include_router(admin_router, prefix=settings.admin_prefix)

    @app.on_event("startup")
    async def startup_event() -> None:  # pragma: no cover - startup hook
        emit_feedback({"event": "startup"})

    return app


app = create_app()
