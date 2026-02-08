"""
Authentication routes for password-based login.
"""

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Request, Response

from ..core import (
    SESSION_COOKIE_NAME,
    get_session_max_age_seconds,
    is_auth_enabled,
    is_cookie_secure,
    is_request_authenticated,
    issue_auth_token,
    verify_auth_password,
)

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    password: str = Field(min_length=1)


class AuthStatusResponse(BaseModel):
    authenticated: bool
    auth_enabled: bool
    token: str | None = None


@router.post("/auth/login", response_model=AuthStatusResponse)
async def login(payload: LoginRequest, response: Response):
    """
    Authenticate with a configured password and set an HTTP-only session cookie.
    """
    if not is_auth_enabled():
        return AuthStatusResponse(authenticated=True, auth_enabled=False, token=None)

    if not verify_auth_password(payload.password):
        raise HTTPException(status_code=401, detail="Invalid password")

    token = issue_auth_token()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=is_cookie_secure(),
        samesite="lax",
        max_age=get_session_max_age_seconds(),
    )
    return AuthStatusResponse(authenticated=True, auth_enabled=True, token=token)


@router.post("/auth/logout", response_model=AuthStatusResponse)
async def logout(response: Response):
    """
    Clear auth session cookie.
    """
    response.delete_cookie(SESSION_COOKIE_NAME)
    return AuthStatusResponse(authenticated=False, auth_enabled=is_auth_enabled(), token=None)


@router.get("/auth/session", response_model=AuthStatusResponse)
async def session_status(request: Request):
    """
    Check whether current request is authenticated.
    """
    auth_enabled = is_auth_enabled()
    authenticated = is_request_authenticated(request)
    return AuthStatusResponse(
        authenticated=authenticated,
        auth_enabled=auth_enabled,
        token=None,
    )
