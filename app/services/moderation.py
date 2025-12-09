"""Moderation orchestration service."""
from __future__ import annotations

from typing import List

from app.config.settings import Settings
from app.engines.base import EngineAggregator
from app.schemas.models import EngineVerdict, ModerationResult
from app.observability import metrics
from app.services.locale import (
    CulturalProfile,
    DEFAULT_PROFILE,
    TranslationBackend,
    DEFAULT_TRANSLATION_BACKEND,
    detect_language,
    profile_from_settings,
    translate,
)


class ModerationService:
    """Run moderation across configured engines and build response payloads."""

    def __init__(
        self,
        aggregator: EngineAggregator,
        settings: Settings,
        *,
        profile: CulturalProfile = DEFAULT_PROFILE,
        translation_backend: TranslationBackend | None = None,
    ) -> None:
        self.aggregator = aggregator
        self.settings = settings
        self.profile = profile
        self.translation_backend = translation_backend or (
            TranslationBackend(live=settings.enable_live_translation)
            if settings
            else DEFAULT_TRANSLATION_BACKEND
        )

    def moderate(self, text: str, *, language: str | None = None) -> ModerationResult:
        resolved_language = language or detect_language(text)
        profile = profile_from_settings(resolved_language, self.settings)
        translated = translate(
            text,
            resolved_language,
            target_lang="en",
            backend=self.translation_backend,
        )
        allowed, severity_scores, votes, action = self.aggregator.evaluate(translated, language=resolved_language)
        severity_scores = {k: profile.adjust(k, v) for k, v in severity_scores.items()}
        # Re-evaluate after cultural adjustments
        allowed, action = self.aggregator._decide(severity_scores)
        if severity_scores:
            worst = max(severity_scores.values())
            metrics.record_severity(worst)
        moderated = ModerationResult(
            allowed=allowed,
            severity_scores=severity_scores,
            engine_votes=votes,
            action=action,
            language=resolved_language,
            translated_input=translated if translated != text else None,
        )
        return moderated

    def classify(self, text: str, *, language: str | None = None) -> List[EngineVerdict]:
        _, _, votes, _ = self.aggregator.evaluate(text, language=language)
        return votes
