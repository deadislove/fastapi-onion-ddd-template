"""
Integration tests for the /api/v1/products endpoints.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _register_and_login(client: AsyncClient, email: str, password: str = "Str0ngP@ss!") -> str:
    """Helper: register a user and return their access token."""
    await client.post(
        "/api/v1/users/register",
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    resp = await client.post(
        "/api/v1/users/login",
        json={"email": email, "password": password},
    )
    return resp.json()["access_token"]


class TestProductCRUD:
    async def test_create_product_success(self, client: AsyncClient):
        token = await _register_and_login(client, "owner@example.com")
        response = await client.post(
            "/api/v1/products/",
            json={"name": "Headphones", "description": "Great sound", "price": 99.99, "stock": 50},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Headphones"
        assert data["price"] == 99.99
        assert data["stock"] == 50

    async def test_create_product_without_auth_returns_401(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/products/",
            json={"name": "Headphones", "description": "", "price": 99.99, "stock": 50},
        )
        assert response.status_code == 401

    async def test_create_duplicate_product_returns_409(self, client: AsyncClient):
        token = await _register_and_login(client, "owner2@example.com")
        payload = {"name": "Keyboard", "description": "", "price": 49.99, "stock": 20}
        await client.post(
            "/api/v1/products/",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        response = await client.post(
            "/api/v1/products/",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 409

    async def test_list_products(self, client: AsyncClient):
        token = await _register_and_login(client, "lister@example.com")
        await client.post(
            "/api/v1/products/",
            json={"name": "Mouse", "description": "", "price": 29.99, "stock": 100},
            headers={"Authorization": f"Bearer {token}"},
        )
        response = await client.get("/api/v1/products/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_get_product_by_id(self, client: AsyncClient):
        token = await _register_and_login(client, "getter@example.com")
        create_resp = await client.post(
            "/api/v1/products/",
            json={"name": "Monitor", "description": "", "price": 299.99, "stock": 10},
            headers={"Authorization": f"Bearer {token}"},
        )
        product_id = create_resp.json()["id"]
        response = await client.get(f"/api/v1/products/{product_id}")
        assert response.status_code == 200
        assert response.json()["id"] == product_id

    async def test_get_nonexistent_product_returns_404(self, client: AsyncClient):
        response = await client.get("/api/v1/products/99999")
        assert response.status_code == 404

    async def test_update_product_success(self, client: AsyncClient):
        token = await _register_and_login(client, "updater@example.com")
        create_resp = await client.post(
            "/api/v1/products/",
            json={"name": "Webcam", "description": "", "price": 79.99, "stock": 30},
            headers={"Authorization": f"Bearer {token}"},
        )
        product_id = create_resp.json()["id"]
        response = await client.patch(
            f"/api/v1/products/{product_id}",
            json={"price": 89.99, "stock": 25},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["price"] == 89.99
        assert data["stock"] == 25

    async def test_update_product_not_owner_returns_401(self, client: AsyncClient):
        owner_token = await _register_and_login(client, "owner3@example.com")
        other_token = await _register_and_login(client, "other@example.com")
        create_resp = await client.post(
            "/api/v1/products/",
            json={"name": "Speaker", "description": "", "price": 59.99, "stock": 15},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        product_id = create_resp.json()["id"]
        response = await client.patch(
            f"/api/v1/products/{product_id}",
            json={"price": 69.99},
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert response.status_code == 401

    async def test_delete_product_success(self, client: AsyncClient):
        token = await _register_and_login(client, "deleter@example.com")
        create_resp = await client.post(
            "/api/v1/products/",
            json={"name": "Tablet", "description": "", "price": 399.99, "stock": 5},
            headers={"Authorization": f"Bearer {token}"},
        )
        product_id = create_resp.json()["id"]
        response = await client.delete(
            f"/api/v1/products/{product_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        # Verify it's gone
        get_resp = await client.get(f"/api/v1/products/{product_id}")
        assert get_resp.status_code == 404
