"""Base definitions for guardrail engines."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Iterable, List, Protocol

from app.schemas.models import EngineVerdict

RiskScores = Dict[str, int]
ActionMap = Dict[int, str]


class GuardrailEngine(Protocol):
    """Protocol for a guardrail engine implementation."""

    name: str

    def run(self, text: str, *, language: str | None = None) -> EngineVerdict:
        """Execute moderation on a piece of text."""


class BaseEngine(ABC):
    """Abstract base class to simplify building engines."""

    name: str

    def __init__(self, *, risk_profiles: RiskScores | None = None) -> None:
        self.risk_profiles = risk_profiles or {}

    @abstractmethod
    def analyze(self, text: str, language: str | None = None) -> EngineVerdict:
        """Return verdict for provided text."""

    def run(self, text: str, *, language: str | None = None) -> EngineVerdict:
        verdict = self.analyze(text, language)
        return verdict


class EngineAggregator:
    """Aggregate results from multiple engines into a unified decision."""

    def __init__(
        self,
        engines: Iterable[GuardrailEngine],
        *,
        severity_threshold: int = 3,
        severity_action_map: ActionMap | None = None,
        category_action_overrides: Dict[str, RiskScores] | None = None,
    ) -> None:
        self.engines = list(engines)
        self.severity_threshold = severity_threshold
        self.severity_action_map = severity_action_map or {0: "allow", 1: "allow", 2: "warn", 3: "block", 4: "block"}
        self.category_action_overrides = category_action_overrides or {}

    def evaluate(
        self, text: str, *, language: str | None = None
    ) -> tuple[bool, Dict[str, int], List[EngineVerdict], str]:
        votes: List[EngineVerdict] = [engine.run(text, language=language) for engine in self.engines]
        severity_scores = self._aggregate_scores(votes)
        allowed, action = self._decide(severity_scores)
        return allowed, severity_scores, votes, action

    def _aggregate_scores(self, votes: List[EngineVerdict]) -> RiskScores:
        scores: RiskScores = {}
        for vote in votes:
            for category, score in vote.details.items():
                scores[category] = max(score, scores.get(category, 0))
            if not vote.details:
                scores[vote.engine] = max(vote.severity, scores.get(vote.engine, 0))
        return scores

    def _decide(self, severity_scores: RiskScores) -> tuple[bool, str]:
        if not severity_scores:
            return True, "allow"
        worst_category = max(severity_scores, key=severity_scores.get)
        worst_value = severity_scores[worst_category]
        category_policy = self.category_action_overrides.get(worst_category, {})
        if worst_value >= self.severity_threshold:
            return False, category_policy.get(worst_value, "block")
        action = category_policy.get(worst_value)
        if action:
            return action != "block", action
        mapped = self.severity_action_map.get(worst_value, "allow")
        return mapped != "block", mapped
