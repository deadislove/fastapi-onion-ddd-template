"""
Logging domain event dispatcher — infrastructure implementation of IEventDispatcher.
Publishes each domain event as one structured JSON log line; swapping this for a
Redis stream / Kafka topic / outbox table later means a new IEventDispatcher impl,
no changes to call sites.

Note: published before the request's DB session commits, so a rollback after
publish still leaves the event "happened" from the outside. No outbox pattern here.
"""
from __future__ import annotations

import logging
from dataclasses import asdict

from app.application.services.event_dispatcher import IEventDispatcher
from app.domain.events import DomainEvent

logger = logging.getLogger("domain.events")


class LoggingEventDispatcher(IEventDispatcher):
    async def publish(self, event: DomainEvent) -> None:
        # Nested under "event_data": some event fields (e.g. name) collide with
        # LogRecord's own reserved attrs if spread as top-level extra kwargs.
        logger.info(
            "domain_event",
            extra={"event_type": type(event).__name__, "event_data": asdict(event)},
        )
