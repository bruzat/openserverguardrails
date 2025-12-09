"""Response middleware to mask PII in JSON payloads."""
from __future__ import annotations

import json
import re
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


PII_PATTERN = re.compile(
    r"(\b\d{3}-\d{2}-\d{4}\b|\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    r"|\+?\d{1,3}[ -]?\(?\d{2,3}\)?[ -]?\d{3}[ -]?\d{4})"
)


def _mask_value(value: Any) -> Any:
    if isinstance(value, str):
        return PII_PATTERN.sub("<redacted>", value)
    if isinstance(value, list):
        return [_mask_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _mask_value(v) for k, v in value.items()}
    return value


class PIIMaskingMiddleware(BaseHTTPMiddleware):
    """Mask common PII patterns in JSON responses."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        response = await call_next(request)
        if isinstance(response, JSONResponse):
            try:
                payload = json.loads(response.body.decode())
            except Exception:
                return response
            masked_payload = _mask_value(payload)
            return JSONResponse(content=masked_payload, status_code=response.status_code, headers=dict(response.headers))
        return response

