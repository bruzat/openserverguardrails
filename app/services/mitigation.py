"""Mitigation utilities for inference-time guardrails."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Tuple


@dataclass
class MitigationPlan:
    """Description of mitigations applied."""

    masked_pii: bool
    removed_categories: Tuple[str, ...]
    message: str
    sanitized_text: str


class MitigationService:
    """Apply lightweight mitigations during inference time."""

    def __init__(self) -> None:
        card_pattern = r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b"
        ssn_pattern = r"\b\d{3}-\d{2}-\d{4}\b"
        email_pattern = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
        phone_pattern = r"\+?\d{1,3}[ -]?\(?\d{2,3}\)?[ -]?\d{3}[ -]?\d{4}"
        self._pii_pattern = re.compile(f"({card_pattern}|{ssn_pattern}|{email_pattern}|{phone_pattern})")

    def apply(self, text: str, *, language: str | None = None) -> MitigationPlan:
        masked = self._pii_pattern.sub("<redacted>", text)
        removed_categories = []
        if masked != text:
            removed_categories.append("pii")
        safe_text = self._strip_violence(masked)
        if safe_text != masked:
            removed_categories.append("violence")
        message = (
            "Mitigation applied"
            if removed_categories or safe_text != text
            else "No mitigation necessary"
        )
        return MitigationPlan(
            masked_pii=masked != text,
            removed_categories=tuple(sorted(set(removed_categories))),
            message=message,
            sanitized_text=safe_text,
        )

    @staticmethod
    def _strip_violence(text: str) -> str:
        """Rewrite obviously violent verbs with neutral terms to match mitigation expectations."""

        violence_keywords = [
            (r"\bkill\b", "stop"),
            (r"\battack\b", "defuse"),
            (r"\bbomb\b", "secure"),
        ]
        sanitized = text
        for pattern, replacement in violence_keywords:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        return sanitized
