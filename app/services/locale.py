"""Locale utilities for detection, translation, and cultural policies."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from app.config.settings import Settings

from langdetect import DetectorFactory, detect

try:  # pragma: no cover - optional dependency
    from deep_translator import GoogleTranslator
except Exception:  # pragma: no cover - optional dependency import failure
    GoogleTranslator = None


DetectorFactory.seed = 0  # deterministic detection during tests


SUPPORTED_LANGUAGES = {"en", "fr", "es", "de", "it", "pt", "zh", "ar", "hi", "ja", "ko"}


class TranslationBackend:
    """Wrap translation to allow real or deterministic behavior."""

    def __init__(self, *, live: bool = False, target_lang: str = "en") -> None:
        self.live = live and GoogleTranslator is not None
        self.target_lang = target_lang

    def translate(self, text: str, source_lang: str, target_lang: str | None = None) -> str:
        """Translate using a live backend when available, else deterministic mapping."""

        target = target_lang or self.target_lang
        if source_lang == target:
            return text
        if self.live and GoogleTranslator is not None:
            try:
                return str(GoogleTranslator(source=source_lang, target=target).translate(text))
            except Exception:  # pragma: no cover - fall back on any runtime failure
                # fall back to deterministic pseudo translation below
                pass
        glossary: Dict[Tuple[str, str], str] = {
            ("fr", "en"): "[fr->en] " + text,
            ("es", "en"): "[es->en] " + text,
            ("de", "en"): "[de->en] " + text,
            ("zh", "en"): "[zh->en] " + text,
            ("ar", "en"): "[ar->en] " + text,
            ("hi", "en"): "[hi->en] " + text,
            ("ja", "en"): "[ja->en] " + text,
            ("ko", "en"): "[ko->en] " + text,
        }
        return glossary.get((source_lang, target), f"[{source_lang}->{target}] {text}")


DEFAULT_TRANSLATION_BACKEND = TranslationBackend()


@dataclass
class CulturalProfile:
    """Rules to adjust severity for cultural sensitivities."""

    name: str
    severity_bias: int = 0
    restricted_categories: Tuple[str, ...] = ()

    def adjust(self, category: str, severity: int) -> int:
        bias = self.severity_bias
        if category in self.restricted_categories:
            bias += 1
        return max(0, min(4, severity + bias))


def detect_language(text: str) -> str:
    """Return ISO 639-1 language code when possible, defaulting to English."""

    if not text.strip():
        return "en"
    try:
        code = detect(text)
    except Exception:  # pragma: no cover - fallback path
        return "en"
    return code or "en"


def translate(
    text: str,
    source_lang: str,
    target_lang: str = "en",
    *,
    backend: TranslationBackend | None = None,
) -> str:
    """Translate text via provided backend with hermetic fallback."""

    return (backend or DEFAULT_TRANSLATION_BACKEND).translate(text, source_lang, target_lang)


DEFAULT_PROFILE = CulturalProfile(
    name="default",
    severity_bias=0,
    restricted_categories=("hate", "self_harm"),
)


def profile_from_settings(language: str, settings: Settings | None = None) -> CulturalProfile:
    """Return a cultural profile derived from settings for the given language."""

    if not settings:
        return DEFAULT_PROFILE
    data = settings.language_profiles.get(language)
    if not data:
        return DEFAULT_PROFILE
    return CulturalProfile(
        name=f"profile_{language}",
        severity_bias=int(data.get("severity_bias", 0)),
        restricted_categories=tuple(data.get("restricted_categories", ())),
    )
