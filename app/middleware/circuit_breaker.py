"""Optional circuit breaker middleware to mitigate harmful generations."""
from __future__ import annotations

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class CircuitBreaker(BaseHTTPMiddleware):
    """Simple counter-based circuit breaker with cooldown."""

    def __init__(
        self, app: Callable, enabled: bool = True, *, failure_threshold: int = 3, reset_after_seconds: int = 30
    ) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.failure_threshold = failure_threshold
        self.reset_after_seconds = reset_after_seconds
        self.failures = 0
        self.tripped_at: float | None = None

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled:
            return await call_next(request)
        if self._is_tripped():
            return Response("Circuit breaker tripped", status_code=503)
        response = await call_next(request)
        if response.status_code >= 500:
            self._register_failure()
        else:
            self._reset()
        return response

    def _is_tripped(self) -> bool:
        if self.tripped_at is None:
            return False
        if time.time() - self.tripped_at >= self.reset_after_seconds:
            # half-open: allow next request to try
            self.failures = 0
            self.tripped_at = None
            return False
        return True

    def _register_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.tripped_at = time.time()

    def _reset(self) -> None:
        self.failures = 0
        self.tripped_at = None
