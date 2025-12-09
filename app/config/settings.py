"""Application configuration using Pydantic settings."""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, List, Optional

from pydantic import BaseSettings, Field, validator


class Settings(BaseSettings):
    """Centralized application settings loaded from environment variables."""

    app_name: str = Field("OpenServerGuardrails", description="Human friendly name of the service")
    api_v1_prefix: str = Field("/v1", description="Base prefix for versioned APIs")
    admin_prefix: str = Field("/admin", description="Prefix for administrative endpoints")
    log_level: str = Field("INFO", description="Logging level")
    allow_origins: List[str] = Field(default_factory=list, description="CORS allowed origins")
    default_engine_chain: List[str] = Field(
        default_factory=lambda: [
            "nemo_guardrails",
            "guardrails_ai",
            "open_guardrails",
            "llm_guard",
            "wildguard",
            "bingoguard",
            "polyguard",
            "aegis_2",
            "llama_guard_3",
            "openai_moderation",
        ],
        description="Default guardrail engine pipeline order",
    )
    default_backend: str = Field(
        "echo",
        description="Default LLM backend identifier (echo for local deterministic backend)",
    )
    hf_endpoint: Optional[str] = Field(
        None, description="Hugging Face text-generation-inference or Inference API endpoint"
    )
    hf_api_token: Optional[str] = Field(None, description="API token for Hugging Face inference")
    vllm_endpoint: Optional[str] = Field(None, description="vLLM OpenAI-compatible endpoint")
    vllm_api_key: Optional[str] = Field(None, description="API key for vLLM endpoint if required")
    vllm_model: Optional[str] = Field(None, description="Optional model name override for vLLM")
    engine_endpoints: Dict[str, str] = Field(
        default_factory=dict,
        description="Optional mapping of engine name to HTTP endpoint for real integrations",
    )
    engine_api_keys: Dict[str, str] = Field(
        default_factory=dict,
        description="Optional API keys per engine name used when engine_endpoints are configured",
    )
    openai_api_key: Optional[str] = Field(None, description="API key for OpenAI backend")
    openai_model: str = Field("gpt-4o-mini", description="Model name for OpenAI backend")
    openai_base_url: Optional[str] = Field(
        None, description="Optional base URL for OpenAI-compatible deployments"
    )
    openai_moderation_model: str = Field(
        "omni-moderation-latest", description="Model name for OpenAI moderation guardrail"
    )
    streaming_chunk_size: int = Field(
        16, ge=4, le=1024, description="Chunk size to use for streaming responses"
    )
    enable_live_translation: bool = Field(
        False,
        description="Enable live translation via deep-translator when installed; defaults to deterministic stub",
    )
    enable_circuit_breaker: bool = Field(True, description="Whether to enable circuit breaker mitigation")
    circuit_breaker_failures: int = Field(3, ge=1, le=20, description="Number of failures before tripping")
    circuit_breaker_reset_seconds: int = Field(30, ge=1, le=600, description="Cooldown before half-open reset")
    severity_threshold: int = Field(3, ge=0, le=4, description="Threshold at which responses are blocked")
    severity_action_map: Dict[int, str] = Field(
        default_factory=lambda: {0: "allow", 1: "allow", 2: "warn", 3: "block", 4: "block"},
        description="Mapping from severity level to action",
    )
    category_action_overrides: Dict[str, Dict[int, str]] = Field(
        default_factory=lambda: {
            "self_harm": {2: "escalate", 3: "block", 4: "block"},
            "criminal_planning": {3: "block", 4: "block"},
        },
        description="Optional per-category severity/action overrides",
    )
    language_profiles: Dict[str, Dict[str, object]] = Field(
        default_factory=lambda: {
            "fr": {"severity_bias": 1, "restricted_categories": ["hate", "harassment"]},
            "ar": {"severity_bias": 1, "restricted_categories": ["religion", "extremism"]},
            "en": {"severity_bias": 0, "restricted_categories": ["self_harm"]},
        },
        description=(
            "Optional per-language cultural profiles specifying severity_bias and restricted_categories. "
            "Allows tuning moderation sensitivity per locale."
        ),
    )
    telemetry_enabled: bool = Field(True, description="Enable OpenTelemetry instrumentation")
    prometheus_enabled: bool = Field(True, description="Expose Prometheus metrics endpoint")
    trulens_enabled: bool = Field(False, description="Enable TruLens feedback instrumentation")
    phoenix_enabled: bool = Field(False, description="Enable Phoenix tracing")
    admin_token: Optional[str] = Field(
        "change-me-admin", description="Bearer token for admin endpoints"
    )
    public_token: Optional[str] = Field(
        "change-me-public", description="Bearer token protecting public APIs"
    )
    require_auth: bool = Field(
        True,
        description="Require bearer authentication on public and admin endpoints."
        " When enabled, tokens must be configured or startup fails.",
    )
    require_tls: bool = Field(False, description="Flag indicating TLS termination is expected upstream")

    class Config:
        env_file = ".env"
        case_sensitive = False

    @validator("log_level")
    def validate_log_level(cls, value: str) -> str:  # pragma: no cover - trivial
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        upper_value = value.upper()
        if upper_value not in allowed:
            raise ValueError(f"Invalid log level: {value}")
        return upper_value


@lru_cache()
def get_settings() -> Settings:
    """Return a cached instance of settings.

    Using lru_cache avoids re-reading environment variables repeatedly.
    """

    return Settings()
