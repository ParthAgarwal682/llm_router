"""Tests for user data isolation: user A cannot access user B's data."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from src.storage import db as _db
from tests.conftest import auth_headers, register_and_login


class TestConversationIsolation:
    def test_user_cannot_read_others_conversation(self, client: TestClient) -> None:
        token_a = register_and_login(client, "alice@example.com", "passAlice123")
        token_b = register_and_login(client, "bob@example.com", "passBob123")

        # Alice creates a conversation
        resp = client.post(
            "/v1/conversations",
            json={"title": "Alice's secret"},
            headers=auth_headers(token_a),
        )
        assert resp.status_code == 201
        conv_id = resp.json()["id"]

        # Bob tries to read it — must get 404, not the data
        resp_b = client.get(f"/v1/conversations/{conv_id}", headers=auth_headers(token_b))
        assert resp_b.status_code == 404

    def test_user_cannot_rename_others_conversation(self, client: TestClient) -> None:
        token_a = register_and_login(client, "alice2@example.com", "passAlice123")
        token_b = register_and_login(client, "bob2@example.com", "passBob123")

        resp = client.post(
            "/v1/conversations",
            json={"title": "Alice's"},
            headers=auth_headers(token_a),
        )
        conv_id = resp.json()["id"]

        resp_b = client.patch(
            f"/v1/conversations/{conv_id}",
            json={"title": "Renamed by Bob"},
            headers=auth_headers(token_b),
        )
        assert resp_b.status_code == 404

        # Verify original title unchanged (via Alice)
        resp_a = client.get(f"/v1/conversations/{conv_id}", headers=auth_headers(token_a))
        assert resp_a.json()["title"] == "Alice's"

    def test_user_cannot_delete_others_conversation(self, client: TestClient) -> None:
        token_a = register_and_login(client, "alice3@example.com", "passAlice123")
        token_b = register_and_login(client, "bob3@example.com", "passBob123")

        resp = client.post(
            "/v1/conversations",
            json={"title": "Alice's chat"},
            headers=auth_headers(token_a),
        )
        conv_id = resp.json()["id"]

        resp_b = client.delete(f"/v1/conversations/{conv_id}", headers=auth_headers(token_b))
        assert resp_b.status_code == 404

        # Still accessible by Alice
        resp_a = client.get(f"/v1/conversations/{conv_id}", headers=auth_headers(token_a))
        assert resp_a.status_code == 200

    def test_conversation_list_scoped_to_user(self, client: TestClient) -> None:
        token_a = register_and_login(client, "alice4@example.com", "passAlice123")
        token_b = register_and_login(client, "bob4@example.com", "passBob123")

        client.post(
            "/v1/conversations",
            json={"title": "Alice's convo"},
            headers=auth_headers(token_a),
        )

        # Bob's conversation list should be empty
        resp_b = client.get("/v1/conversations", headers=auth_headers(token_b))
        assert resp_b.status_code == 200
        assert resp_b.json() == []

    def test_cannot_read_others_messages(self, client: TestClient) -> None:
        token_a = register_and_login(client, "alice5@example.com", "passAlice123")
        token_b = register_and_login(client, "bob5@example.com", "passBob123")

        resp = client.post(
            "/v1/conversations",
            json={"title": "Private chat"},
            headers=auth_headers(token_a),
        )
        conv_id = resp.json()["id"]

        # Bob tries to list messages in Alice's conversation
        resp_b = client.get(
            f"/v1/conversations/{conv_id}/messages",
            headers=auth_headers(token_b),
        )
        assert resp_b.status_code == 404


class TestRequestIsolation:
    def test_user_cannot_read_others_request(self, client: TestClient, tmp_db: Path) -> None:
        """Create a request row directly in DB and verify other users can't see it."""
        token_a = register_and_login(client, "alice6@example.com", "passAlice123")
        token_b = register_and_login(client, "bob6@example.com", "passBob123")

        # Get Alice's user_id from /me
        alice_id = client.get("/v1/auth/me", headers=auth_headers(token_a)).json()["id"]

        # Insert a request for Alice directly
        req_id = _db.create_request(
            prompt="Alice's secret prompt",
            response_text="secret answer",
            tier="simple",
            model_used="llama_8b",
            model_id="meta-llama/llama-3.1-8b-instruct",
            cost_usd=0.001,
            baseline_cost_usd=0.005,
            latency_ms=100.0,
            user_id=alice_id,
            db_path=tmp_db,
        )

        # Alice can see it
        resp_a = client.get(f"/v1/requests/{req_id}", headers=auth_headers(token_a))
        assert resp_a.status_code == 200

        # Bob gets 404
        resp_b = client.get(f"/v1/requests/{req_id}", headers=auth_headers(token_b))
        assert resp_b.status_code == 404

    def test_unauthenticated_cannot_read_request(self, client: TestClient, tmp_db: Path) -> None:
        req_id = _db.create_request(
            prompt="test",
            response_text="ans",
            tier="simple",
            model_used="llama_8b",
            model_id="meta-llama/llama-3.1-8b-instruct",
            cost_usd=0.0,
            baseline_cost_usd=0.0,
            latency_ms=0.0,
            db_path=tmp_db,
        )
        resp = client.get(f"/v1/requests/{req_id}")
        assert resp.status_code == 401
