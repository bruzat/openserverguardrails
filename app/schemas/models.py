"""Pydantic schemas for API requests and responses."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    """Represents a chat message."""

    role: str = Field(..., description="speaker role (user/assistant/system)")
    content: str = Field(..., description="message content")
    language: Optional[str] = Field(None, description="ISO language code when known")


class EngineVerdict(BaseModel):
    """Verdict from a single guardrail engine."""

    engine: str
    allowed: bool
    severity: int = Field(..., ge=0, le=4)
    categories: List[str] = Field(default_factory=list)
    details: Dict[str, float] = Field(default_factory=dict, description="Optional extra scores per category")


class ModerationResult(BaseModel):
    """Aggregated moderation outcome."""

    allowed: bool
    severity_scores: Dict[str, int] = Field(default_factory=dict)
    engine_votes: List[EngineVerdict] = Field(default_factory=list)
    action: str = Field(..., description="Action taken for the request")
    language: Optional[str] = Field(None, description="Detected or provided language")
    translated_input: Optional[str] = Field(None, description="Translated text when applicable")


class ChatCompletionRequest(BaseModel):
    """Request body for chat completions."""

    messages: List[Message]
    stream: bool = False
    language: Optional[str] = Field(None, description="Optional hint for language selection")


class ChatCompletionResponse(BaseModel):
    """Response for chat completions including moderation metadata."""

    content: str
    moderated: ModerationResult


class ModerationRequest(BaseModel):
    """Request for /moderations endpoint."""

    input: str
    language: Optional[str] = None


class ModerationResponse(BaseModel):
    """Response for /moderations endpoint."""

    moderated: ModerationResult


class ClassificationRequest(BaseModel):
    """Request for classification endpoint."""

    text: str
    language: Optional[str] = None


class ClassificationResponse(BaseModel):
    """Response for classification endpoint."""

    votes: List[EngineVerdict]


class MitigationRequest(BaseModel):
    """Request for inference mitigation endpoint."""

    text: str
    engine: Optional[str] = None
    language: Optional[str] = None


class MitigationResponse(BaseModel):
    """Response for inference mitigation endpoint."""

    mitigated: bool
    message: str
    sanitized_text: Optional[str] = Field(None, description="Redacted or rewritten content when mitigation applied")
