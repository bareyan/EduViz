"""
Password-based authentication helpers.

This module provides:
- Password verification
- Stateless signed session token handling
- Public path matching for auth exemptions
- Request authentication checks (cookie or bearer token)
"""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Iterable

from fastapi import Request

from .runtime import parse_bool_env

SESSION_COOKIE_NAME = "eduviz_session"
AUTH_BEARER_PREFIX = "Bearer "

PUBLIC_PATHS_EXACT = {
    "/",
    "/health",
    "/auth/login",
    "/auth/logout",
    "/auth/session",
    "/openapi.json",
    "/docs",
    "/redoc",
}

PUBLIC_PATH_PREFIXES = (
    "/docs/",
    "/redoc/",
    "/static/",
    "/outputs/",
)


def _auth_password() -> str:
    return os.getenv("AUTH_PASSWORD", "").strip()


def _auth_secret() -> str:
    # Separate secret allows rotating signing material without changing password.
    return os.getenv("AUTH_SECRET", "eduviz-auth-secret").strip()


def _auth_enabled_flag() -> bool:
    return parse_bool_env(os.getenv("AUTH_ENABLED"), default=True)


def is_auth_enabled() -> bool:
    return _auth_enabled_flag() and bool(_auth_password())


def _custom_public_paths() -> set[str]:
    raw = os.getenv("AUTH_OPEN_PATHS", "").strip()
    if not raw:
        return set()
    return {path.strip() for path in raw.split(",") if path.strip()}


def is_public_path(path: str) -> bool:
    if path in PUBLIC_PATHS_EXACT:
        return True
    if path in _custom_public_paths():
        return True
    return any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)


def _token_material() -> str:
    password = _auth_password()
    secret = _auth_secret()
    digest = hashlib.sha256(f"{password}:{secret}".encode("utf-8")).hexdigest()
    return digest


def issue_auth_token() -> str:
    return _token_material()


def verify_auth_password(password: str) -> bool:
    configured = _auth_password()
    if not configured:
        return False
    return hmac.compare_digest(password, configured)


def verify_auth_token(token: str) -> bool:
    if not is_auth_enabled():
        return True
    expected = _token_material()
    return hmac.compare_digest(token, expected)


def _extract_bearer_token(authorization_header: str | None) -> str | None:
    if not authorization_header:
        return None
    if not authorization_header.startswith(AUTH_BEARER_PREFIX):
        return None
    return authorization_header[len(AUTH_BEARER_PREFIX):].strip() or None


def extract_request_token(request: Request) -> str | None:
    bearer = _extract_bearer_token(request.headers.get("Authorization"))
    if bearer:
        return bearer

    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie_token:
        return cookie_token

    return None


def is_request_authenticated(request: Request) -> bool:
    if not is_auth_enabled():
        return True
    token = extract_request_token(request)
    if not token:
        return False
    return verify_auth_token(token)


def get_session_max_age_seconds() -> int:
    raw = os.getenv("AUTH_SESSION_MAX_AGE_SECONDS", "604800").strip()  # 7 days
    try:
        max_age = int(raw)
    except ValueError:
        return 604800
    return max(60, max_age)


def is_cookie_secure() -> bool:
    return parse_bool_env(os.getenv("AUTH_COOKIE_SECURE"), default=False)


def get_cookie_samesite() -> str:
    raw = os.getenv("AUTH_COOKIE_SAMESITE", "lax").strip().lower()
    if raw not in {"lax", "strict", "none"}:
        return "lax"
    return raw


def get_cookie_domain() -> str | None:
    raw = os.getenv("AUTH_COOKIE_DOMAIN", "").strip()
    return raw or None


def get_cookie_path() -> str:
    raw = os.getenv("AUTH_COOKIE_PATH", "/").strip()
    return raw or "/"


def list_public_paths() -> dict[str, Iterable[str]]:
    return {
        "exact": sorted(PUBLIC_PATHS_EXACT.union(_custom_public_paths())),
        "prefixes": list(PUBLIC_PATH_PREFIXES),
    }
