"""Resolve the signed-in user from Azure App Service Easy Auth headers.

When Easy Auth is enabled, App Service injects the authenticated user's stable
id and display name into every request. Locally (no auth in front) we fall back
to a single 'local' user so development keeps working unchanged.
"""
from fastapi import Request

LOCAL_USER = "local"


def current_user(request: Request) -> str:
    """Stable per-user id (used as the internal user_id on trades)."""
    return request.headers.get("x-ms-client-principal-id") or LOCAL_USER


def current_user_name(request: Request) -> str:
    """Human-readable name/email of the signed-in user, if available."""
    return request.headers.get("x-ms-client-principal-name") or LOCAL_USER
