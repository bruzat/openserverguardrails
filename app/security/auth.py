"""Authentication helpers for public and admin endpoints."""
from __future__ import annotations

from fastapi import Header, HTTPException, status


def require_bearer_token(expected: str | None, header_value: str | None, *, audience: str, required: bool) -> None:
    """Validate a bearer token for the given audience.

    If `required` is True, the token must be present and match. If not required
    and no expected token is configured, requests are allowed to proceed.
    """

    if not expected and not required:
        return
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing token for {audience}",
        )
    if not header_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing token for {audience}",
        )
    if header_value != f"Bearer {expected}":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token for {audience}",
        )


def public_auth_dependency(expected_public_token: str | None, *, required: bool):
    """Return a dependency that validates the Authorization header for public APIs."""

    async def dependency(authorization: str | None = Header(default=None, convert_underscores=False)) -> None:
        require_bearer_token(expected_public_token, authorization, audience="public", required=required)

    return dependency


def admin_auth_dependency(expected_admin_token: str | None, *, required: bool):
    """Return a dependency that validates the Authorization header for admin APIs."""

    async def dependency(authorization: str | None = Header(default=None, convert_underscores=False)) -> None:
        require_bearer_token(expected_admin_token, authorization, audience="admin", required=required)

    return dependency


__all__ = ["public_auth_dependency", "admin_auth_dependency", "require_bearer_token"]
