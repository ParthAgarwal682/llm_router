"""FastAPI dependencies: get_current_user, rate limiting, daily cap enforcement.

Rate limiting:
- In-process sliding window per user (requests per minute).
- Documented limitation: does not span multiple uvicorn workers.
  Add Redis for multi-worker deployments.

Daily cap:
- Enforced via DB query against today's UTC request count.
- Configured per-user via users.daily_request_limit.
"""

from __future__ import annotations

import asyncio
import collections
import os
import time
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.api.auth import TokenError, decode_access_token
from src.storage import db
from src.storage.db import UserRow

# ---------------------------------------------------------------------------
# JWT bearer extraction
# ---------------------------------------------------------------------------

_bearer = HTTPBearer(auto_error=False)


def _extract_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    request: Request,
) -> str | None:
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    if "token" in request.query_params:
        return request.query_params["token"]
    return None


# ---------------------------------------------------------------------------
# Rate limiting (in-process sliding window)
# ---------------------------------------------------------------------------

RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "20"))  # requests per minute per user
_WINDOW_SECONDS = 60.0

# user_id → deque of timestamps (floats)
_rate_windows: dict[str, collections.deque] = collections.defaultdict(
    lambda: collections.deque()
)
_rate_lock = asyncio.Lock()


async def _check_rate_limit(user_id: str) -> None:
    """Raise 429 if the user has exceeded RATE_LIMIT_RPM requests in the last 60 s."""
    now = time.monotonic()
    async with _rate_lock:
        window = _rate_windows[user_id]
        # Drop timestamps older than 60 s
        while window and now - window[0] > _WINDOW_SECONDS:
            window.popleft()
        if len(window) >= RATE_LIMIT_RPM:
            oldest = window[0]
            retry_after = int(_WINDOW_SECONDS - (now - oldest)) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "rate_limited",
                    "message": f"Too many requests. Limit: {RATE_LIMIT_RPM} per minute. "
                               f"Try again in {retry_after}s.",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )
        window.append(now)


# ---------------------------------------------------------------------------
# Daily cap enforcement
# ---------------------------------------------------------------------------

async def _check_daily_cap(user: UserRow) -> None:
    """Raise 429 if the user has hit their daily_request_limit."""
    count = db.count_user_requests_today(user.id)
    if count >= user.daily_request_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "daily_limit_reached",
                "message": f"Daily request limit of {user.daily_request_limit} reached. "
                           "Resets at UTC midnight.",
                "limit": user.daily_request_limit,
                "used": count,
            },
        )


# ---------------------------------------------------------------------------
# Core dependency
# ---------------------------------------------------------------------------

async def get_current_user(
    token: Annotated[str | None, Depends(_extract_token)],
) -> UserRow:
    """Decode the Bearer token and return the authenticated user.

    Raises 401 on any auth failure. Never raises 403.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_error
    try:
        payload = decode_access_token(token)
    except TokenError:
        raise credentials_error

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise credentials_error

    user = db.get_user_by_id(user_id)
    if user is None or not user.is_active:
        raise credentials_error
    return user


async def get_current_user_with_limits(
    user: Annotated[UserRow, Depends(get_current_user)],
) -> UserRow:
    """Like get_current_user but also enforces rate limit and daily cap.

    Use this dependency on endpoints that consume quota (completions, chat).
    Auth-only endpoints (me, conversations list) use get_current_user directly.
    """
    await _check_rate_limit(user.id)
    await _check_daily_cap(user)
    return user


# ---------------------------------------------------------------------------
# Input validation constants
# ---------------------------------------------------------------------------

MAX_PROMPT_LENGTH = int(os.getenv("MAX_PROMPT_LENGTH", "8000"))   # characters
MAX_CONVERSATION_MESSAGES = int(os.getenv("MAX_CONVERSATION_MESSAGES", "200"))
