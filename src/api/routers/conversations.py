"""Conversation CRUD endpoints — all user-scoped."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.api.deps import get_current_user
from src.storage import db
from src.storage.db import UserRow

router = APIRouter(prefix="/v1/conversations", tags=["conversations"])

MAX_TITLE_LENGTH = 200


class ConversationCreateRequest(BaseModel):
    title: str = Field(default="New conversation", max_length=MAX_TITLE_LENGTH)
    session_id: str = Field(default="")   # optional for legacy compat


class ConversationRenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=MAX_TITLE_LENGTH)


@router.post("", status_code=201)
def create_conversation(
    body: ConversationCreateRequest,
    current_user: Annotated[UserRow, Depends(get_current_user)],
) -> dict[str, Any]:
    """Create a new conversation owned by the current user."""
    conv_id = db.create_conversation(
        session_id=body.session_id or current_user.id,
        title=body.title,
        user_id=current_user.id,
    )
    conv = db.get_conversation(conv_id, user_id=current_user.id)
    return conv or {"id": conv_id, "title": body.title}


@router.get("")
def list_conversations(
    current_user: Annotated[UserRow, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict]:
    """List conversations for the current user, newest first."""
    # Use user_id for scoping (session_id is a legacy field; pass user_id as session)
    return db.list_conversations(
        session_id=current_user.id,
        limit=limit,
        user_id=current_user.id,
    )


@router.get("/{conversation_id}")
def get_conversation(
    conversation_id: str,
    current_user: Annotated[UserRow, Depends(get_current_user)],
) -> dict[str, Any]:
    conv = db.get_conversation(conversation_id, user_id=current_user.id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.patch("/{conversation_id}")
def rename_conversation(
    conversation_id: str,
    body: ConversationRenameRequest,
    current_user: Annotated[UserRow, Depends(get_current_user)],
) -> dict[str, str]:
    ok = db.update_conversation_title(
        conversation_id,
        body.title,
        user_id=current_user.id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"id": conversation_id, "title": body.title}


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: str,
    current_user: Annotated[UserRow, Depends(get_current_user)],
) -> None:
    ok = db.delete_conversation(conversation_id, user_id=current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.get("/{conversation_id}/messages")
def get_messages(
    conversation_id: str,
    current_user: Annotated[UserRow, Depends(get_current_user)],
) -> list[dict]:
    """Return all messages in a conversation (user-scoped)."""
    # Verify ownership first
    conv = db.get_conversation(conversation_id, user_id=current_user.id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return db.get_conversation_messages(conversation_id, user_id=current_user.id)
