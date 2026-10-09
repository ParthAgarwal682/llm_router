"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import functools
import inspect
import os
from pathlib import Path
from typing import Generator

import pytest

# Set test env vars BEFORE importing the app
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-production")
os.environ.setdefault("OPENROUTER_API_KEY", "sk-or-v1-test-key")

from fastapi.testclient import TestClient

from src.api.main import app
from src.storage import db as _db


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """A fresh SQLite DB in a temp directory for each test."""
    db_path = tmp_path / "test.db"
    _db.init_db(db_path)
    return db_path


def _make_db_wrapper(orig_fn, tmp_db: Path):
    """Return a wrapper that injects db_path=tmp_db unless already supplied."""
    sig = inspect.signature(orig_fn)

    @functools.wraps(orig_fn)
    def _wrapped(*args, **kwargs):
        # Only inject if the function accepts db_path AND it's not already bound
        if "db_path" in sig.parameters and "db_path" not in kwargs:
            # Also check it wasn't passed positionally
            param_names = list(sig.parameters.keys())
            db_path_pos = param_names.index("db_path")
            if len(args) <= db_path_pos:
                kwargs["db_path"] = tmp_db
        return orig_fn(*args, **kwargs)

    return _wrapped


@pytest.fixture()
def client(tmp_db: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """TestClient with a fresh isolated DB for each test."""
    import src.storage.db as db_mod

    monkeypatch.setattr(db_mod, "DEFAULT_DB_PATH", tmp_db)

    for fn_name in [
        "init_db", "create_user", "get_user_by_email", "get_user_by_id",
        "count_user_requests_today", "store_refresh_token", "get_refresh_token",
        "revoke_refresh_token", "revoke_all_user_refresh_tokens",
        "create_request", "update_request", "get_request", "list_requests",
        "get_stats", "get_user_stats", "get_session_stats",
        "create_conversation", "list_conversations", "get_conversation",
        "update_conversation_title", "delete_conversation",
        "touch_conversation", "get_conversation_messages",
    ]:
        orig = getattr(db_mod, fn_name)
        monkeypatch.setattr(db_mod, fn_name, _make_db_wrapper(orig, tmp_db))

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def register_and_login(client: TestClient, email: str, password: str) -> str:
    """Helper: register a user and return the access token."""
    resp = client.post("/v1/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
