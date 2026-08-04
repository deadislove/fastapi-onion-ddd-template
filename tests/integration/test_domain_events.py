"""
Integration tests verifying domain events are actually published through the full
DI-wired stack (service -> IEventDispatcher), not just queued and discarded.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.domain.events import (
    ProductCreatedEvent,
    ProductDeletedEvent,
    ProductUpdatedEvent,
    UserDeletedEvent,
    UserRegisteredEvent,
    UserUpdatedEvent,
)
from app.infrastructure.database.models import UserModel

pytestmark = pytest.mark.asyncio


async def _register_and_login(client: AsyncClient, email: str, password: str = "Str0ngP@ss!") -> str:
    await client.post(
        "/api/v1/users/register",
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    resp = await client.post("/api/v1/users/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


class TestUserEvents:
    async def test_register_publishes_user_registered_event(self, client, captured_events):
        response = await client.post(
            "/api/v1/users/register",
            json={"email": "events-user@example.com", "password": "Str0ngP@ss!", "full_name": "Events User"},
        )
        user_id = response.json()["id"]

        registered = [e for e in captured_events.events if isinstance(e, UserRegisteredEvent)]
        assert len(registered) == 1
        assert registered[0].user_id == user_id
        assert registered[0].email == "events-user@example.com"

    async def test_update_profile_publishes_user_updated_event(self, client, captured_events):
        token = await _register_and_login(client, "events-update@example.com")
        captured_events.events.clear()

        await client.patch(
            "/api/v1/users/me",
            json={"full_name": "Updated Name"},
            headers={"Authorization": f"Bearer {token}"},
        )

        updated = [e for e in captured_events.events if isinstance(e, UserUpdatedEvent)]
        assert len(updated) == 1

    async def test_delete_user_publishes_user_deleted_event(self, client, captured_events, db_session):
        # DELETE /users/{id} requires a superuser, and there's no registration flag for
        # that (by design) — promote directly via the DB row, reusing the token issued
        # before promotion (is_superuser isn't embedded in the JWT; it's re-checked
        # against the DB on every request via get_current_superuser).
        admin_token = await _register_and_login(client, "events-admin@example.com")
        admin_me = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {admin_token}"})
        admin_id = admin_me.json()["id"]
        await db_session.execute(update(UserModel).where(UserModel.id == admin_id).values(is_superuser=True))

        victim_token = await _register_and_login(client, "events-victim@example.com")
        victim_me = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {victim_token}"})
        victim_id = victim_me.json()["id"]
        captured_events.events.clear()

        response = await client.delete(
            f"/api/v1/users/{victim_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200

        deleted = [e for e in captured_events.events if isinstance(e, UserDeletedEvent)]
        assert len(deleted) == 1
        assert deleted[0].user_id == victim_id


class TestProductEvents:
    async def test_create_product_publishes_product_created_event(self, client, captured_events):
        token = await _register_and_login(client, "events-owner@example.com")
        response = await client.post(
            "/api/v1/products/",
            json={"name": "Event Widget", "description": "", "price": 19.99, "stock": 10},
            headers={"Authorization": f"Bearer {token}"},
        )
        product_id = response.json()["id"]

        created = [e for e in captured_events.events if isinstance(e, ProductCreatedEvent)]
        assert len(created) == 1
        assert created[0].product_id == product_id
        assert created[0].name == "Event Widget"

    async def test_update_product_publishes_product_updated_event(self, client, captured_events):
        token = await _register_and_login(client, "events-updater@example.com")
        create_resp = await client.post(
            "/api/v1/products/",
            json={"name": "Update Widget", "description": "", "price": 9.99, "stock": 5},
            headers={"Authorization": f"Bearer {token}"},
        )
        product_id = create_resp.json()["id"]
        captured_events.events.clear()

        await client.patch(
            f"/api/v1/products/{product_id}",
            json={"price": 12.99},
            headers={"Authorization": f"Bearer {token}"},
        )

        updated = [e for e in captured_events.events if isinstance(e, ProductUpdatedEvent)]
        assert len(updated) == 1
        assert updated[0].product_id == product_id

    async def test_delete_product_publishes_product_deleted_event(self, client, captured_events):
        token = await _register_and_login(client, "events-deleter@example.com")
        create_resp = await client.post(
            "/api/v1/products/",
            json={"name": "Delete Widget", "description": "", "price": 5.99, "stock": 1},
            headers={"Authorization": f"Bearer {token}"},
        )
        product_id = create_resp.json()["id"]
        captured_events.events.clear()

        await client.delete(
            f"/api/v1/products/{product_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        deleted = [e for e in captured_events.events if isinstance(e, ProductDeletedEvent)]
        assert len(deleted) == 1
        assert deleted[0].product_id == product_id
