"""Tests for auth endpoints: register, login, refresh, logout, me."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_and_login


class TestRegister:
    def test_register_success(self, client: TestClient) -> None:
        resp = client.post(
            "/v1/auth/register",
            json={"email": "alice@example.com", "password": "securepass123"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "access_token" in body
        assert body["user"]["email"] == "alice@example.com"
        # password_hash must never appear
        assert "password_hash" not in body["user"]
        assert "password" not in body["user"]

    def test_register_duplicate_email(self, client: TestClient) -> None:
        payload = {"email": "dup@example.com", "password": "securepass123"}
        assert client.post("/v1/auth/register", json=payload).status_code == 201
        resp = client.post("/v1/auth/register", json=payload)
        assert resp.status_code == 409

    def test_register_weak_password(self, client: TestClient) -> None:
        resp = client.post(
            "/v1/auth/register",
            json={"email": "test@example.com", "password": "short"},
        )
        assert resp.status_code == 422

    def test_register_invalid_email(self, client: TestClient) -> None:
        resp = client.post(
            "/v1/auth/register",
            json={"email": "not-an-email", "password": "securepass123"},
        )
        assert resp.status_code == 422

    def test_register_sets_refresh_cookie(self, client: TestClient) -> None:
        resp = client.post(
            "/v1/auth/register",
            json={"email": "cookie@example.com", "password": "securepass123"},
        )
        assert resp.status_code == 201
        assert "refresh_token" in resp.cookies


class TestLogin:
    def test_login_success(self, client: TestClient) -> None:
        client.post(
            "/v1/auth/register",
            json={"email": "login@example.com", "password": "mypassword123"},
        )
        resp = client.post(
            "/v1/auth/login",
            json={"email": "login@example.com", "password": "mypassword123"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_wrong_password(self, client: TestClient) -> None:
        client.post(
            "/v1/auth/register",
            json={"email": "wp@example.com", "password": "rightpass123"},
        )
        resp = client.post(
            "/v1/auth/login",
            json={"email": "wp@example.com", "password": "wrongpass123"},
        )
        assert resp.status_code == 401

    def test_login_nonexistent_email(self, client: TestClient) -> None:
        resp = client.post(
            "/v1/auth/login",
            json={"email": "nobody@example.com", "password": "whatever123"},
        )
        assert resp.status_code == 401

    def test_login_case_insensitive_email(self, client: TestClient) -> None:
        client.post(
            "/v1/auth/register",
            json={"email": "Case@Example.COM", "password": "mypassword123"},
        )
        resp = client.post(
            "/v1/auth/login",
            json={"email": "case@example.com", "password": "mypassword123"},
        )
        assert resp.status_code == 200


class TestMe:
    def test_me_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/v1/auth/me")
        assert resp.status_code == 401

    def test_me_returns_user_info(self, client: TestClient) -> None:
        token = register_and_login(client, "me@example.com", "securepass123")
        resp = client.get("/v1/auth/me", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "me@example.com"
        assert "password_hash" not in body
        assert "requests_today" in body
        assert "daily_limit_remaining" in body

    def test_me_invalid_token(self, client: TestClient) -> None:
        resp = client.get("/v1/auth/me", headers={"Authorization": "Bearer badtoken"})
        assert resp.status_code == 401


class TestRefreshAndLogout:
    def test_refresh_rotates_token(self, client: TestClient) -> None:
        resp = client.post(
            "/v1/auth/register",
            json={"email": "refresh@example.com", "password": "securepass123"},
        )
        assert resp.status_code == 201
        old_token = resp.json()["access_token"]

        refresh_resp = client.post("/v1/auth/refresh")
        assert refresh_resp.status_code == 200
        new_token = refresh_resp.json()["access_token"]
        # New token should differ from old
        assert new_token != old_token

    def test_logout_clears_cookie(self, client: TestClient) -> None:
        resp = client.post(
            "/v1/auth/register",
            json={"email": "logout@example.com", "password": "securepass123"},
        )
        token = resp.json()["access_token"]
        logout_resp = client.post("/v1/auth/logout", headers=auth_headers(token))
        assert logout_resp.status_code == 204
