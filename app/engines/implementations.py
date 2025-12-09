"""Lightweight heuristic implementations of the required guardrail engines."""
from __future__ import annotations

import re
import json
from typing import Dict, List, Optional

import requests

try:  # pragma: no cover - optional dependency provided by requirements
    from openai import OpenAI
except Exception:  # pragma: no cover - handled gracefully for environments without openai
    OpenAI = None

from app.engines.base import BaseEngine
from app.schemas.models import EngineVerdict


DEFAULT_PATTERNS: Dict[str, Dict[str, List[str]]] = {
    "violence": {"keywords": ["attack", "kill", "bomb", "assassinate"]},
    "self_harm": {"keywords": ["suicide", "self-harm", "end my life"]},
    "hate": {"keywords": ["hate", "racist", "bigot"]},
    "pii": {"keywords": ["passport", "ssn", "credit card"]},
}


class ExternalEngine(BaseEngine):
    """Engine that calls an HTTP endpoint when configured, falling back to heuristics.

    This enables plugging real moderation frameworks (NeMo, GuardrailsAI, OpenGuardrails,
    WildGuard, BingoGuard, PolyGuard, AEGIS 2.0, Llama Guard 3) without changing service code.
    """

    def __init__(
        self,
        name: str,
        *,
        endpoint: str,
        api_key: Optional[str] = None,
        severity_bias: int = 0,
    ) -> None:
        super().__init__()
        self.name = name
        self.endpoint = endpoint
        self.api_key = api_key
        self.fallback = HeuristicEngine(name=name, severity_bias=severity_bias)

    def analyze(self, text: str, language: str | None = None) -> EngineVerdict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {"text": text, "language": language}
        try:
            response = requests.post(self.endpoint, headers=headers, data=json.dumps(payload), timeout=5)
            response.raise_for_status()
            data = response.json()
            severity = min(4, int(data.get("severity", 0)))
            categories = data.get("categories", []) or []
            details = {k: min(4, int(v)) for k, v in data.get("details", {}).items()}
            allowed = data.get("allowed", severity < 3)
            return EngineVerdict(
                engine=self.name,
                allowed=bool(allowed),
                severity=severity,
                categories=list(categories),
                details=details or {cat: severity for cat in categories},
            )
        except Exception:
            return self.fallback.analyze(text, language)


class HeuristicEngine(BaseEngine):
    """Base engine built on keyword heuristics with configurable severity."""

    def __init__(self, name: str, *, severity_bias: int = 0) -> None:
        super().__init__()
        self.name = name
        self.severity_bias = severity_bias

    def analyze(self, text: str, language: str | None = None) -> EngineVerdict:
        findings: Dict[str, float] = {}
        lowered = text.lower()
        for category, config in DEFAULT_PATTERNS.items():
            for keyword in config["keywords"]:
                if re.search(re.escape(keyword), lowered, re.IGNORECASE):
                    findings[category] = max(findings.get(category, 0), 3 + self.severity_bias)
        severity = max(findings.values(), default=0)
        allowed = severity < 3
        return EngineVerdict(
            engine=self.name,
            allowed=allowed,
            severity=min(4, severity),
            categories=list(findings.keys()),
            details={k: min(4, int(v)) for k, v in findings.items()},
        )


class MultilingualEngine(HeuristicEngine):
    """Engine that slightly boosts severity for unknown languages to stay safe."""

    def analyze(self, text: str, language: str | None = None) -> EngineVerdict:  # pragma: no cover - wrapper
        verdict = super().analyze(text, language)
        if language and language not in {"en", "fr", "es", "de", "it", "pt", "zh"}:
            verdict.severity = min(4, verdict.severity + 1)
            verdict.allowed = verdict.severity < 3
        return verdict


class CircuitBreakerEngine(HeuristicEngine):
    """Engine representing mitigation during inference."""

    def analyze(self, text: str, language: str | None = None) -> EngineVerdict:
        verdict = super().analyze(text, language)
        if verdict.severity >= 3:
            verdict.details["mitigated"] = 1
        return verdict


class NemoGuardrailsEngine(HeuristicEngine):
    def __init__(self) -> None:
        super().__init__("nemo_guardrails", severity_bias=0)


class GuardrailsAIEngine(HeuristicEngine):
    def __init__(self) -> None:
        super().__init__("guardrails_ai", severity_bias=0)


class OpenGuardrailsEngine(HeuristicEngine):
    def __init__(self) -> None:
        super().__init__("open_guardrails", severity_bias=1)


class LLMGuardEngine(HeuristicEngine):
    def __init__(self) -> None:
        super().__init__("llm_guard", severity_bias=0)


class OpenAIModerationEngine(HeuristicEngine):
    """Real moderation via OpenAI when configured, with heuristic fallback."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "omni-moderation-latest",
        settings=None,
    ) -> None:
        super().__init__("openai_moderation", severity_bias=0)
        self.model = model
        self._client = None
        resolved_api_key = api_key or getattr(settings, "openai_api_key", None)
        resolved_base_url = base_url or getattr(settings, "openai_base_url", None)
        resolved_model = getattr(settings, "openai_moderation_model", None)
        if resolved_model:
            self.model = resolved_model
        if resolved_api_key and OpenAI is not None:
            self._client = OpenAI(api_key=resolved_api_key, base_url=resolved_base_url)

    def analyze(self, text: str, language: str | None = None) -> EngineVerdict:
        if not self._client:
            return super().analyze(text, language)
        try:
            response = self._client.moderations.create(model=self.model, input=text)
            result = response.results[0]
            details: Dict[str, int] = {}
            for category, score in result.category_scores.items():
                # Convert floating scores to severity buckets 0-4
                details[category] = min(4, int(round(score * 4)))
            severity = max(details.values(), default=0)
            return EngineVerdict(
                engine=self.name,
                allowed=not result.flagged,
                severity=severity,
                categories=list(details.keys()),
                details=details,
            )
        except Exception:
            return super().analyze(text, language)


class WildGuardEngine(MultilingualEngine):
    def __init__(self) -> None:
        super().__init__("wildguard", severity_bias=0)


class BingoGuardEngine(HeuristicEngine):
    def __init__(self) -> None:
        super().__init__("bingoguard", severity_bias=1)


class PolyGuardEngine(MultilingualEngine):
    def __init__(self) -> None:
        super().__init__("polyguard", severity_bias=0)


class AEGIS2Engine(HeuristicEngine):
    def __init__(self) -> None:
        super().__init__("aegis_2", severity_bias=1)


class LlamaGuard3Engine(MultilingualEngine):
    def __init__(self) -> None:
        super().__init__("llama_guard_3", severity_bias=0)


ENGINE_REGISTRY = {
    "nemo_guardrails": NemoGuardrailsEngine,
    "guardrails_ai": GuardrailsAIEngine,
    "open_guardrails": OpenGuardrailsEngine,
    "llm_guard": LLMGuardEngine,
    "openai_moderation": OpenAIModerationEngine,
    "wildguard": WildGuardEngine,
    "bingoguard": BingoGuardEngine,
    "polyguard": PolyGuardEngine,
    "aegis_2": AEGIS2Engine,
    "llama_guard_3": LlamaGuard3Engine,
}
