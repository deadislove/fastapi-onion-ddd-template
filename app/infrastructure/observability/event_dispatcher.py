"""
Logging domain event dispatcher — infrastructure implementation of IEventDispatcher.
Publishes each domain event as one structured JSON log line. This is the simplest
possible "real" dispatcher: no new broker/queue to run, but every event is genuinely
published (not just collected and discarded) and is trivial to swap for a Redis
stream / Kafka topic / outbox-table publisher later without touching call sites —
they only depend on IEventDispatcher.

Caveat: this is dispatched from within the request's DB session, before the
session's own commit (see infrastructure/database/session.py's get_db_session).
So on a rollback after publish, the event has still "happened" from the outside —
there's no dual-write guarantee here. A production system with stronger delivery
requirements would use a transactional outbox instead.
"""
from __future__ import annotations

import logging
from dataclasses import asdict

from app.application.services.event_dispatcher import IEventDispatcher
from app.domain.events import DomainEvent

logger = logging.getLogger("domain.events")


class LoggingEventDispatcher(IEventDispatcher):
    async def publish(self, event: DomainEvent) -> None:
        # Nested under "event_data" rather than spread as top-level extra kwargs: several
        # DomainEvent subclasses have fields (e.g. ProductCreatedEvent.name) that collide
        # with LogRecord's own reserved attribute names (LogRecord.name is the logger's
        # name) — spreading them raises `KeyError: Attempt to overwrite 'name' in LogRecord`.
        logger.info(
            "domain_event",
            extra={"event_type": type(event).__name__, "event_data": asdict(event)},
        )
