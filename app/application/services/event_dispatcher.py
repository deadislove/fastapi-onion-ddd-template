"""
Domain event dispatcher — application-layer abstraction for publishing domain events
once they've been persisted. Infrastructure provides the concrete implementation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.events import DomainEvent


class IEventDispatcher(ABC):
    """Abstract interface for publishing domain events — implemented in infrastructure."""

    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        ...

    async def publish_all(self, events: list[DomainEvent]) -> None:
        for event in events:
            await self.publish(event)
