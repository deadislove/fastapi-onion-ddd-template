"""
Unit tests for the real LoggingEventDispatcher (not the in-memory fake used by the
integration tests) — catches issues like DomainEvent fields colliding with LogRecord's
own reserved attribute names, e.g. ProductCreatedEvent.name vs LogRecord.name.
"""
from __future__ import annotations

import logging

import pytest

from app.domain.events import (
    ProductCreatedEvent,
    ProductDeletedEvent,
    ProductUpdatedEvent,
    UserDeletedEvent,
    UserRegisteredEvent,
    UserUpdatedEvent,
)
from app.infrastructure.observability.event_dispatcher import LoggingEventDispatcher

pytestmark = pytest.mark.asyncio

ALL_EVENTS = [
    UserRegisteredEvent(user_id=1, email="alice@example.com"),
    UserUpdatedEvent(user_id=1),
    UserDeletedEvent(user_id=1),
    ProductCreatedEvent(product_id=1, owner_id=1, name="Widget"),
    ProductUpdatedEvent(product_id=1),
    ProductDeletedEvent(product_id=1),
]


@pytest.mark.parametrize("event", ALL_EVENTS, ids=lambda e: type(e).__name__)
async def test_publish_does_not_raise_for_every_event_type(event, caplog):
    dispatcher = LoggingEventDispatcher()
    with caplog.at_level(logging.INFO, logger="domain.events"):
        await dispatcher.publish(event)
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.event_type == type(event).__name__
    assert record.event_data["event_id"] == event.event_id
