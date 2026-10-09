"""JWT creation/verification and password hashing for the router auth system.

Design decisions:
- HS256 tokens; JWT_SECRET loaded from env (required at startup, no default).
- Access token: short-lived (ACCESS_TOKEN_EXPIRE_MINUTES, default 15).
- Refresh token: long-lived (REFRESH_TOKEN_EXPIRE_DAYS, default 7).
  Stored in DB with a jti claim for revocation.
- Passwords: bcrypt via passlib (cost factor 12).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

# ---------------------------------------------------------------------------
# Config from env
# ---------------------------------------------------------------------------

def _require_env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing required env var: {key}")
    return val


def get_jwt_secret() -> str:
    """Return JWT_SECRET from env — raises at first call if missing."""
    return _require_env("JWT_SECRET")


ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
ALGORITHM = "HS256"

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------

def create_access_token(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=ALGORITHM)


def create_refresh_token(user_id: str) -> tuple[str, str, datetime]:
    """Return (encoded_jwt, jti, expires_at).

    The jti is stored in the DB so we can revoke individual tokens.
    """
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "jti": jti,
        "exp": expire,
    }
    token = jwt.encode(payload, get_jwt_secret(), algorithm=ALGORITHM)
    return token, jti, expire


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------

class TokenError(Exception):
    """Raised when a JWT cannot be decoded or has wrong type."""


def decode_access_token(token: str) -> dict:
    """Return decoded payload or raise TokenError."""
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[ALGORITHM])
    except JWTError as exc:
        raise TokenError(f"Invalid access token: {exc}") from exc

    if payload.get("type") != "access":
        raise TokenError("Token is not an access token")
    return payload


def decode_refresh_token(token: str) -> dict:
    """Return decoded payload or raise TokenError."""
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[ALGORITHM])
    except JWTError as exc:
        raise TokenError(f"Invalid refresh token: {exc}") from exc

    if payload.get("type") != "refresh":
        raise TokenError("Token is not a refresh token")
    return payload
