"""
Integration tests for the /api/v1/users endpoints.
Uses in-memory SQLite and the full FastAPI app stack.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestUserRegistration:
    async def test_register_success(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/users/register",
            json={
                "email": "alice@example.com",
                "password": "Str0ngP@ss!",
                "full_name": "Alice Smith",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "alice@example.com"
        assert data["full_name"] == "Alice Smith"
        assert data["is_active"] is True
        assert "id" in data

    async def test_register_duplicate_email_returns_409(self, client: AsyncClient):
        payload = {
            "email": "bob@example.com",
            "password": "Str0ngP@ss!",
            "full_name": "Bob Jones",
        }
        await client.post("/api/v1/users/register", json=payload)
        response = await client.post("/api/v1/users/register", json=payload)
        assert response.status_code == 409

    async def test_register_short_password_returns_422(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/users/register",
            json={
                "email": "charlie@example.com",
                "password": "short",
                "full_name": "Charlie",
            },
        )
        assert response.status_code == 422

    async def test_register_invalid_email_returns_422(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/users/register",
            json={
                "email": "not-an-email",
                "password": "Str0ngP@ss!",
                "full_name": "Test User",
            },
        )
        assert response.status_code == 422


class TestUserLogin:
    async def test_login_success(self, client: AsyncClient):
        # Register first
        await client.post(
            "/api/v1/users/register",
            json={
                "email": "dave@example.com",
                "password": "Str0ngP@ss!",
                "full_name": "Dave",
            },
        )
        # Login
        response = await client.post(
            "/api/v1/users/login",
            json={"email": "dave@example.com", "password": "Str0ngP@ss!"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password_returns_401(self, client: AsyncClient):
        await client.post(
            "/api/v1/users/register",
            json={
                "email": "eve@example.com",
                "password": "Str0ngP@ss!",
                "full_name": "Eve",
            },
        )
        response = await client.post(
            "/api/v1/users/login",
            json={"email": "eve@example.com", "password": "WrongPassword!"},
        )
        assert response.status_code == 401

    async def test_login_nonexistent_user_returns_401(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/users/login",
            json={"email": "ghost@example.com", "password": "Str0ngP@ss!"},
        )
        assert response.status_code == 401


class TestTokenSecurity:
    async def _register_and_login(self, client: AsyncClient, email: str = "heidi@example.com") -> dict:
        await client.post(
            "/api/v1/users/register",
            json={"email": email, "password": "Str0ngP@ss!", "full_name": "Heidi"},
        )
        login_resp = await client.post(
            "/api/v1/users/login",
            json={"email": email, "password": "Str0ngP@ss!"},
        )
        return login_resp.json()

    async def test_refresh_token_cannot_be_used_as_access_token(self, client: AsyncClient):
        tokens = await self._register_and_login(client, "ivan@example.com")
        response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
        )
        assert response.status_code == 401

    async def test_access_token_cannot_be_used_to_refresh(self, client: AsyncClient):
        tokens = await self._register_and_login(client, "judy@example.com")
        response = await client.post(
            "/api/v1/users/refresh",
            json={"refresh_token": tokens["access_token"]},
        )
        assert response.status_code == 401

    async def test_refresh_rotates_and_invalidates_old_refresh_token(self, client: AsyncClient):
        tokens = await self._register_and_login(client, "kevin@example.com")
        first_refresh = await client.post(
            "/api/v1/users/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert first_refresh.status_code == 200

        # Replaying the original (now-rotated) refresh token must fail.
        replay = await client.post(
            "/api/v1/users/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert replay.status_code == 401

    async def test_logout_revokes_access_token(self, client: AsyncClient):
        tokens = await self._register_and_login(client, "laura@example.com")
        logout_resp = await client.post(
            "/api/v1/users/logout",
            json={},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert logout_resp.status_code == 200

        me_resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert me_resp.status_code == 401

    async def test_logout_revokes_supplied_refresh_token(self, client: AsyncClient):
        tokens = await self._register_and_login(client, "mallory@example.com")
        logout_resp = await client.post(
            "/api/v1/users/logout",
            json={"refresh_token": tokens["refresh_token"]},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert logout_resp.status_code == 200

        refresh_resp = await client.post(
            "/api/v1/users/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert refresh_resp.status_code == 401


class TestUserProfile:
    async def _register_and_login(self, client: AsyncClient, email: str = "frank@example.com"):
        await client.post(
            "/api/v1/users/register",
            json={"email": email, "password": "Str0ngP@ss!", "full_name": "Frank"},
        )
        login_resp = await client.post(
            "/api/v1/users/login",
            json={"email": email, "password": "Str0ngP@ss!"},
        )
        return login_resp.json()["access_token"]

    async def test_get_me_success(self, client: AsyncClient):
        token = await self._register_and_login(client)
        response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "frank@example.com"

    async def test_get_me_without_token_returns_401(self, client: AsyncClient):
        response = await client.get("/api/v1/users/me")
        assert response.status_code == 401

    async def test_update_me_success(self, client: AsyncClient):
        token = await self._register_and_login(client, "grace@example.com")
        response = await client.patch(
            "/api/v1/users/me",
            json={"full_name": "Grace Updated"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["full_name"] == "Grace Updated"


class TestHealthCheck:
    async def test_health_check(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
