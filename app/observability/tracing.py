"""Observability utilities wrapping OpenTelemetry, TruLens, and Phoenix."""
from __future__ import annotations

import logging
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

logger = logging.getLogger(__name__)


def initialize_tracing(enabled: bool) -> None:
    """Configure a minimal OpenTelemetry tracer that exports to stdout.

    The console exporter avoids the need for an external collector while still
    producing real spans that can be inspected during tests or local debugging.
    """

    if not enabled:
        return
    provider = TracerProvider(resource=Resource.create({"service.name": "guardrails-server"}))
    processor = BatchSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    logger.info("OpenTelemetry tracing initialized with console exporter")


def initialize_trulens(enabled: bool) -> None:  # pragma: no cover - integration hook
    if enabled:
        logger.info("TruLens instrumentation enabled (hook only)")


def initialize_phoenix(enabled: bool) -> None:  # pragma: no cover - integration hook
    if enabled:
        logger.info("Phoenix instrumentation enabled (hook only)")


def emit_feedback(metadata: dict[str, Any]) -> None:
    """Record feedback for evaluation and log for observability."""

    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("feedback") as span:
        for key, value in metadata.items():
            span.set_attribute(f"feedback.{key}", str(value))
    logger.debug("Feedback: %s", metadata)
