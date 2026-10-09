"""Auth endpoints: register, login, refresh, logout, me."""

from __future__ import annotations

import sqlite3
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field, field_validator

from src.api.auth import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
    TokenError,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from src.api.deps import MAX_PROMPT_LENGTH, get_current_user
from src.storage import db
from src.storage.db import UserRow

router = APIRouter(prefix="/v1/auth", tags=["auth"])

# httpOnly cookie name for refresh token
REFRESH_COOKIE = "refresh_token"
COOKIE_MAX_AGE = REFRESH_TOKEN_EXPIRE_DAYS * 86400  # seconds


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=False,       # set to True in production behind HTTPS
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
        path="/v1/auth",    # only sent to auth routes
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE, path="/v1/auth")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Password cannot be whitespace only")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/register", response_model=AuthResponse, status_code=201)
def register(body: RegisterRequest, response: Response) -> AuthResponse:
    """Create a new account. Sets httpOnly refresh token cookie."""
    try:
        user = db.create_user(
            email=body.email,
            password_hash=hash_password(body.password),
        )
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    access_token = create_access_token(user.id, user.email)
    refresh_token, jti, expires_at = create_refresh_token(user.id)
    db.store_refresh_token(
        jti=jti,
        user_id=user.id,
        expires_at=expires_at.isoformat(),
    )
    _set_refresh_cookie(response, refresh_token)
    return AuthResponse(access_token=access_token, user=user.to_public_dict())


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, response: Response) -> AuthResponse:
    """Authenticate and return an access token. Sets httpOnly refresh token cookie."""
    user = db.get_user_by_email(body.email)
    # Constant-time check to prevent timing attacks on email existence.
    # Dummy hash is for a short password to avoid the 72-byte bcrypt limit.
    _dummy_hash = "$2b$12$eImiTXuWVxfM37uY4JANjQ==invaliddummyhashfortimingnone"
    if user is None:
        # run verify to consume similar time; ignore result
        try:
            verify_password("dummy", _dummy_hash)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive.",
        )

    access_token = create_access_token(user.id, user.email)
    refresh_token, jti, expires_at = create_refresh_token(user.id)
    db.store_refresh_token(
        jti=jti,
        user_id=user.id,
        expires_at=expires_at.isoformat(),
    )
    _set_refresh_cookie(response, refresh_token)
    return AuthResponse(access_token=access_token, user=user.to_public_dict())


@router.post("/refresh", response_model=AuthResponse)
def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
) -> AuthResponse:
    """Rotate refresh token and return a new access token."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token.",
    )
    if not refresh_token:
        raise credentials_error

    try:
        payload = decode_refresh_token(refresh_token)
    except TokenError:
        raise credentials_error

    jti: str | None = payload.get("jti")
    user_id: str | None = payload.get("sub")
    if not jti or not user_id:
        raise credentials_error

    stored = db.get_refresh_token(jti)
    if stored is None or stored["revoked"]:
        raise credentials_error

    user = db.get_user_by_id(user_id)
    if user is None or not user.is_active:
        raise credentials_error

    # Rotate: revoke old token, issue new one
    db.revoke_refresh_token(jti)
    new_access = create_access_token(user.id, user.email)
    new_refresh, new_jti, new_expires = create_refresh_token(user.id)
    db.store_refresh_token(
        jti=new_jti,
        user_id=user.id,
        expires_at=new_expires.isoformat(),
    )
    _set_refresh_cookie(response, new_refresh)
    return AuthResponse(access_token=new_access, user=user.to_public_dict())


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    current_user: Annotated[UserRow, Depends(get_current_user)],
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
) -> None:
    """Revoke the refresh token and clear the cookie."""
    if refresh_token:
        try:
            payload = decode_refresh_token(refresh_token)
            jti = payload.get("jti")
            if jti:
                db.revoke_refresh_token(jti)
        except TokenError:
            pass  # cookie invalid — still clear it
    _clear_refresh_cookie(response)


@router.get("/me")
def me(current_user: Annotated[UserRow, Depends(get_current_user)]) -> dict[str, Any]:
    """Return the authenticated user's profile and today's usage count."""
    requests_today = db.count_user_requests_today(current_user.id)
    return {
        **current_user.to_public_dict(),
        "requests_today": requests_today,
        "daily_limit_remaining": max(0, current_user.daily_request_limit - requests_today),
    }
