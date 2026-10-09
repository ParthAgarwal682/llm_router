"""Per-user stats and profile endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from src.api.deps import get_current_user
from src.storage import db
from src.storage.db import UserRow

router = APIRouter(prefix="/v1/me", tags=["me"])


@router.get("/stats")
def my_stats(
    current_user: Annotated[UserRow, Depends(get_current_user)],
    range: str = Query(default="30d", pattern="^(7d|30d|all)$"),
) -> dict[str, Any]:
    """Return cost savings and usage stats for the current user.

    range: '7d' = last 7 days, '30d' = last 30 days, 'all' = all time.
    """
    days: int | None
    if range == "7d":
        days = 7
    elif range == "30d":
        days = 30
    else:
        days = None

    return db.get_user_stats(current_user.id, days=days)
