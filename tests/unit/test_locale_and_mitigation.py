"""Unit coverage for locale utilities and mitigation service."""
from app.middleware.circuit_breaker import CircuitBreaker
from app.config.settings import Settings
from app.services.locale import (
    CulturalProfile,
    TranslationBackend,
    detect_language,
    profile_from_settings,
    translate,
)
from app.services.mitigation import MitigationService


def test_detect_language_handles_known_phrase() -> None:
    assert detect_language("Bonjour le monde") == "fr"


def test_translate_adds_prefix_for_non_english() -> None:
    translated = translate("Hola", "es", target_lang="en")
    assert translated.startswith("[es->en]")


def test_translate_uses_backend_when_requested(monkeypatch) -> None:
    calls = {}

    class DummyBackend(TranslationBackend):
        def __init__(self) -> None:
            super().__init__(live=False)

        def translate(self, text: str, source_lang: str, target_lang: str | None = None) -> str:  # type: ignore[override]
            calls["used"] = True
            return f"dummy-{source_lang}-{target_lang}-{text}"

    backend = DummyBackend()
    translated = translate("Hallo", "de", target_lang="en", backend=backend)
    assert translated.startswith("dummy-de-en-")
    assert calls.get("used") is True


def test_cultural_profile_adjusts_restricted_categories() -> None:
    profile = CulturalProfile(name="strict", severity_bias=0, restricted_categories=("hate",))
    assert profile.adjust("hate", 2) == 3
    assert profile.adjust("other", 2) == 2


def test_mitigation_masks_pii_patterns() -> None:
    service = MitigationService()
    plan = service.apply("Card 4242 4242 4242 4242")
    assert plan.masked_pii is True
    assert "pii" in plan.removed_categories
    assert "<redacted>" in plan.sanitized_text


def test_profile_from_settings_applies_bias() -> None:
    settings = Settings(language_profiles={"fr": {"severity_bias": 1, "restricted_categories": ["self_harm"]}})
    profile = profile_from_settings("fr", settings)
    assert profile.severity_bias == 1
    assert profile.adjust("self_harm", 2) == 4


def test_mitigation_rewrites_violence() -> None:
    service = MitigationService()
    plan = service.apply("We should attack")
    assert "defuse" in plan.sanitized_text


def test_circuit_breaker_trips_after_failures() -> None:
    breaker = CircuitBreaker(lambda req: None, enabled=True, failure_threshold=2, reset_after_seconds=1)
    breaker._register_failure()
    assert breaker._is_tripped() is False
    breaker._register_failure()
    assert breaker._is_tripped() is True
